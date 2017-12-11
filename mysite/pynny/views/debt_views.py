#!/usr/bin/env python3
"""
File: debt_views.py
Author: Zachary King

Implements views/handlers for Debt-related requests
"""

from django.shortcuts import render
from datetime import datetime
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
import decimal

from ..models import Debt, Transaction
from ..utils import notifications


class DebtsView(LoginRequiredMixin, View):
    """Handles requests to the /debt/ resources"""
    current_tab = 'debts'

    @staticmethod
    def get(request):
        """Get the user's debts objects"""
        context = {
            'current_tab': DebtsView.current_tab,
            'debts': Debt.objects.filter(user=request.user)
        }
        return render(request, 'pynny/debt/debts.html', context=context)

    @staticmethod
    def post(request):
        """Parse form-data and create a new debt"""
        context = {'current_tab': DebtsView.current_tab}
        name = request.POST.get('name', None)
        try:
            goal = float(request.POST.get('goal', 0.0))
        except ValueError:
            goal = 0.0

        try:
            due_date = datetime.strptime(request.POST.get('due_date', ''), '%Y-%m-%d').date()
        except ValueError:
            due_date = None

        notify = 'notify' in request.POST
        delete = 'delete' in request.POST
        is_receiving = request.POST.get('isReceiving', 'no') == 'yes'

        # Check if the debt name exists already
        if Debt.objects.filter(user=request.user, name=name):
            context['alerts'] = {'errors': ['A debt already exists with that name']}
            context['debts'] = Debt.objects.filter(user=request.user)
            return render(request, 'pynny/debt/debts.html', context=context)

        # Create the new debt
        Debt(name=name, goal=goal, balance=decimal.Decimal('0'),
             is_receiving=is_receiving,
             due_date=due_date if due_date else None,
             delete_on_completion=delete,
             notify_on_completion=notify, completed=False, hidden=False, user=request.user).save()

        context['alerts'] = {'success': ['New debt created successfully!']}
        context['debts'] = Debt.objects.filter(user=request.user)
        return render(request, 'pynny/debt/debts.html', context=context, status=201)


class SingleDebtView(LoginRequiredMixin, View):
    """Handles requests to a single debt resource"""
    current_tab = 'debts'

    @staticmethod
    def pre_process(request, debt_id):
        context = {'current_tab': SingleDebtView.current_tab}
        try:
            debt = Debt.objects.get(id=debt_id)
        except Debt.DoesNotExist:
            context['alerts'] = {'errors': ['That debt does not exist.']}
            context['debts'] = Debt.objects.filter(user=request.user)
            return False, render(request, 'pynny/debt/debts.html', context=context, status=404)

        if debt.user != request.user:
            context['alerts'] = {'errors': ['That debt does not exist.']}
            context['debts'] = Debt.objects.filter(user=request.user)
            return False, render(request, 'pynny/debt/debts.html', context=context, status=403)

        return True, debt

    @staticmethod
    def get(request, debt_id):
        context = {'current_tab': SingleDebtView.current_tab}
        success, resp = SingleDebtView.pre_process(request, debt_id)
        if not success:
            return resp

        context['debt'] = resp
        context['transactions'] = Transaction.objects.filter(user=request.user, debt=resp)
        return render(request, 'pynny/debt/one_debt.html', context=context)

    @staticmethod
    def post(request, debt_id):
        context = {'current_tab': SingleDebtView.current_tab}
        success, resp = SingleDebtView.pre_process(request, debt_id)
        if not success:
            return resp

        debt = resp
        action = request.POST.get('action', '').lower()

        if action == 'edit_complete':
            name = request.POST.get('name', None)
            goal = request.POST.get('goal', None)
            if goal is not None:
                try:
                    goal = float(goal)
                except ValueError:
                    goal = None
            due_date = request.POST.get('due_date', None)
            if due_date is not None:
                try:
                    due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                except ValueError:
                    due_date = None
            notify = True if 'notify' in request.POST else False
            delete = True if 'delete' in request.POST else False
            is_receiving = request.POST.get('isReceiving', 'no') == 'yes'

            # Make sure the new name doesn't already exist
            if name != debt.name and Debt.objects.filter(user=request.user, name=name):
                context['alerts'] = {'errors': ['A debt already exists with that name.']}
                context['debts'] = Debt.objects.filter(user=request.user)
                return render(request, 'pynny/debt/debts.html', context=context)

            # Data is fine, update the debt
            debt.name = name if name is not None else debt.name
            debt.goal = goal if goal is not None else debt.goal
            debt.due_date = due_date if due_date is not None else debt.due_date
            debt.notify_on_completion = notify
            debt.delete_on_completion = delete
            debt.is_receiving = is_receiving
            if debt.goal <= debt.balance:
                complete_debt(debt)
                context['alerts'] = {'success': ['Debt updated successfully.']}
            else:
                debt.save()

            context['debts'] = Debt.objects.filter(user=request.user)
            return render(request, 'pynny/debt/debts.html', context=context, status=200)

        elif action == 'delete':
            debt.delete()
            context['alerts'] = {'success': ['Debt deleted successfully.']}
            return render(request, 'pynny/debt/debts.html', context=context)


def complete_debt(debt):
    debt.completed = True
    debt.save()

    if debt.notify_on_completion:
        notifications.notify_debt_complete(debt)
    if debt.delete_on_completion:
        debt.delete()
