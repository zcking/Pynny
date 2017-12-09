#!/usr/bin/env python3
"""
File: savings_views.py
Author: Zachary King

Implements views/handlers for Savings-related requests
"""

from django.shortcuts import render
from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
import decimal

from ..models import Wallet, Budget, Transaction, Savings
from ..utils import notifications


class SavingsView(LoginRequiredMixin, View):
    """Handles requests to the /savings/ resources"""
    current_tab = 'savings'

    @staticmethod
    def get(request):
        """Get the user's Saving objects"""
        context = {
            'current_tab': SavingsView.current_tab,
            'savings': Savings.objects.filter(user=request.user)
        }
        return render(request, 'pynny/savings/savings.html', context=context)

    @staticmethod
    def post(request):
        """Parse form-data and create a new Saving"""
        context = {'current_tab': SavingsView.current_tab}
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

        # Check if the Saving name exists already
        if Savings.objects.filter(user=request.user, name=name):
            context['alerts'] = {'errors': ['A saving already exists with that name']}
            context['savings'] = Savings.objects.filter(user=request.user)
            return render(request, 'pynny/savings/savings.html', context=context)

        # Create the new Saving
        Savings(name=name, goal=goal, balance=decimal.Decimal('0'),
                due_date=due_date if due_date else None,
                delete_on_completion=delete,
                notify_on_completion=notify, completed=False, hidden=False, user=request.user).save()

        context['alerts'] = {'success': ['New Saving created successfully!']}
        context['savings'] = Savings.objects.filter(user=request.user)
        return render(request, 'pynny/savings/savings.html', context=context, status=201)


class SingleSavingView(LoginRequiredMixin, View):
    """Handles requests to a single savings resource"""
    current_tab = 'savings'

    @staticmethod
    def pre_process(request, savings_id):
        context = {'current_tab': SingleSavingView.current_tab}
        try:
            saving = Savings.objects.get(id=savings_id)
        except Savings.DoesNotExist:
            context['alerts'] = {'errors': ['That saving does not exist.']}
            context['savings'] = Savings.objects.filter(user=request.user)
            return False, render(request, 'pynny/savings/savings.html', context=context, status=404)

        if saving.user != request.user:
            context['alerts'] = {'errors': ['That saving does not exist.']}
            context['savings'] = Savings.objects.filter(user=request.user)
            return False, render(request, 'pynny/savings/savings.html', context=context, status=403)

        return True, saving

    @staticmethod
    def get(request, savings_id):
        context = {'current_tab': SingleSavingView.current_tab}
        success, resp = SingleSavingView.pre_process(request, savings_id)
        if not success:
            return resp

        context['saving'] = resp
        context['transactions'] = Transaction.objects.filter(user=request.user, saving=resp)
        return render(request, 'pynny/savings/one_saving.html', context=context)

    @staticmethod
    def post(request, savings_id):
        context = {'current_tab': SingleSavingView.current_tab}
        success, resp = SingleSavingView.pre_process(request, savings_id)
        if not success:
            return resp

        saving = resp
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

            # Make sure the new name doesn't already exist
            if name != saving.name and Savings.objects.filter(user=request.user, name=name):
                context['alerts'] = {'errors': ['A saving already exists with that name.']}
                context['savings'] = Savings.objects.filter(user=request.user)
                return render(request, 'pynny/savings/savings.html', context=context)

            # Data is fine, update the Saving
            saving.name = name if name is not None else saving.name
            saving.goal = goal if goal is not None else saving.goal
            saving.due_date = due_date if due_date is not None else saving.due_date
            saving.notify_on_completion = notify
            saving.delete_on_completion = delete
            if saving.goal <= saving.balance:
                complete_saving(saving)
                context['alerts'] = {'success': ['Saving updated successfully.']}
            else:
                saving.save()

            context['savings'] = Savings.objects.filter(user=request.user)
            return render(request, 'pynny/savings/savings.html', context=context, status=200)

        elif action == 'delete':
            saving.delete()
            context['alerts'] = {'success': ['Saving deleted successfully.']}
            return render(request, 'pynny/savings/savings.html', context=context)


def complete_saving(saving):
    saving.completed = True
    saving.save()

    if saving.notify_on_completion:
        notifications.notify_saving_complete(saving)
    if saving.delete_on_completion:
        saving.delete()
