#!/usr/bin/env python3
"""
File: budget_views.py
Author: Zachary King

Implements the views/handlers for Budget-related requests
"""

from django.views import View
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
import decimal
from datetime import date

from ..models import Budget, BudgetCategory, Wallet, Transaction


class RenewBudgetView(LoginRequiredMixin, View):
    @staticmethod
    def get(request):
        renewed = set()
        today = date.today()
        last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
        last_month_budgets = Budget.objects.filter(user=request.user, month__contains=date.strftime(last_month, '%Y-%m'))

        for budget in last_month_budgets:
            if budget.budget_id not in renewed:
                renewed_budget = Budget.objects.get(pk=budget.pk)
                renewed_budget.pk = None
                renewed_budget.month = date.today()
                renewed_budget.balance = decimal.Decimal('0')
                renewed_budget.save()
                renewed.add(budget.budget_id)
            return budgets(request)


class BudgetsView(LoginRequiredMixin, View):
    @staticmethod
    def get(request):
        """Get a User's Budgets"""
        data = dict()
        data['current_tab'] = 'budgets'

        # Get the wallets for this user
        data['budgets'] = Budget.objects.filter(user=request.user, month__contains=date.strftime(date.today(), '%Y-%m'))
        today = date.today()
        last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
        data['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                           month__contains=date.strftime(last_month, '%Y-%m'))
        data['categories'] = BudgetCategory.objects.filter(user=request.user)
        data['wallets'] = Wallet.objects.filter(user=request.user)

        return render(request, 'pynny/budgets/budgets.html', context=data)

    @staticmethod
    def post(request):
        """Create a new Budget for the logged in user"""
        # Get the form data from the request
        _category = int(request.POST['category'])
        _goal = float(request.POST['goal'])
        _start_balance = decimal.Decimal(0.0)
        _wallet = int(request.POST['wallet'])

        category = BudgetCategory.objects.get(id=_category)
        wallet = Wallet.objects.get(id=_wallet)

        # Calculate the starting balance
        for transaction in Transaction.objects.filter(category=category):
            _start_balance += transaction.amount

        # Check if the budget already exists
        if Budget.objects.filter(user=request.user, category=category, wallet=wallet,
                                 month__contains=date.strftime(date.today(), '%Y-%m')):
            data = {'alerts': {'errors': [
                '<strong>Oops!</strong> A Budget already exists for that Wallet and Category, for this month']}}
            today = date.today()
            last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
            data['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                               month__contains=date.strftime(last_month, '%Y-%m'))
            data['budgets'] = Budget.objects.filter(user=request.user,
                                                    month__contains=date.strftime(date.today(), '%Y-%m'))
            data['current_tab'] = 'budgets'
            return render(request, 'pynny/budgets/new_budget.html', context=data)

        # Create the new Budget
        try:
            latest_budget = Budget.objects.latest('budget_id')
        except Budget.DoesNotExist:
            latest_budget = None

        new_id = latest_budget.budget_id + 1 if latest_budget is not None else 0
        Budget(category=category, wallet=wallet, goal=_goal, balance=_start_balance, user=request.user,
               budget_id=new_id).save()
        data = {'alerts': {'success': ['<strong>Done!</strong> New Budget created successfully!']}}
        data['budgets'] = Budget.objects.filter(user=request.user, month__contains=date.strftime(date.today(), '%Y-%m'))
        today = date.today()
        last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
        data['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                           month__contains=date.strftime(last_month, '%Y-%m'))
        data['categories'] = BudgetCategory.objects.filter(user=request.user)
        data['wallets'] = Wallet.objects.filter(user=request.user)
        data['current_tab'] = 'budgets'
        return render(request, 'pynny/budgets/budgets.html', context=data, status=201)


class SingleBudgetView(LoginRequiredMixin, View):
    @staticmethod
    def pre_process(request, budget_id):
        # Check if the budget is owned by the logged in user
        context = dict()
        try:
            budget = Budget.objects.get(id=budget_id)
        except Budget.DoesNotExist:
            # DNE
            context['budgets'] = Budget.objects.filter(user=request.user,
                                                    month__contains=date.strftime(date.today(), '%Y-%m'))
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            today = date.today()
            last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
            context['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                               month__contains=date.strftime(last_month, '%Y-%m'))
            context['wallets'] = Wallet.objects.filter(user=request.user)
            context['alerts'] = {'errors': ['<strong>Oh snap!</strong> That Budget does not exist.']}
            context['current_tab'] = 'budgets'
            return False, render(request, 'pynny/budgets/budgets.html', context=context, status=404)

        if budget.user != request.user:
            context['budgets'] = Budget.objects.filter(user=request.user,
                                                    month__contains=date.strftime(date.today(), '%Y-%m'))
            today = date.today()
            last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
            context['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                               month__contains=date.strftime(last_month, '%Y-%m'))
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['wallets'] = Wallet.objects.filter(user=request.user)
            context['alerts'] = {
                'errors': ['<strong>Oh snap!</strong> That Budget isn\'t yours! You don\'t have permission to view it']}
            context['current_tab'] = 'budgets'
            return False, render(request, 'pynny/budgets/budgets.html', context=context, status=403)

    @staticmethod
    def get(request, budget_id):
        # Show the specific Budget data
        context = dict()
        successful, failed_resp = SingleBudgetView.pre_process(request, budget_id)
        if not successful:
            return failed_resp

        budget = Budget.objects.get(id=budget_id)
        context['budget'] = budget
        today = date.today()
        last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
        context['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                           month__contains=date.strftime(last_month, '%Y-%m'))
        context['categories'] = BudgetCategory.objects.filter(user=request.user)
        context['wallets'] = Wallet.objects.filter(user=request.user)
        context['transactions'] = Transaction.objects.filter(category=budget.category).order_by('-created_time')
        context['current_tab'] = 'budgets'
        return render(request, 'pynny/budgets/one_budget.html', context=context)

    @staticmethod
    def post(request, budget_id):
        successful, failed_resp = SingleBudgetView.pre_process(request, budget_id)
        if not successful:
            return failed_resp

        budget = Budget.objects.get(id=budget_id)
        context = dict()

        # What kind of action is being performed on the budget?
        action = request.POST['action'].lower()

        if action == 'delete':
            # Delete the Budget
            budget.delete()

            # And return them to the budgets page
            context['budgets'] = Budget.objects.filter(user=request.user,
                                                    month__contains=date.strftime(date.today(), '%Y-%m'))
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            today = date.today()
            last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
            context['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                               month__contains=date.strftime(last_month, '%Y-%m'))
            context['wallets'] = Wallet.objects.filter(user=request.user)
            context['alerts'] = {'success': ['<strong>Done!</strong> Budget was deleted successfully']}
            context['current_tab'] = 'budgets'
            return render(request, 'pynny/budgets/budgets.html', context=context)
        elif action == 'edit':
            # Render the edit_budget view
            context['budget'] = budget
            today = date.today()
            last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
            context['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                               month__contains=date.strftime(last_month, '%Y-%m'))
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['wallets'] = Wallet.objects.filter(user=request.user)
            context['current_tab'] = 'budgets'
            return render(request, 'pynny/budgets/edit_budget.html', context=context)
        elif action == 'edit_complete':
            # Get the form data from the request
            _category = int(request.POST['category'])
            _wallet = int(request.POST['wallet'])
            _goal = float(request.POST['goal'])

            category = BudgetCategory.objects.get(id=_category)
            wallet = Wallet.objects.get(id=_wallet)

            # Edit the Budget
            budget.category = category
            budget.wallet = wallet
            budget.goal = _goal
            budget.save()

            context = {'alerts': {'success': ['<strong>Done!</strong> Budget updated successfully!']}}
            today = date.today()
            last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
            context['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                               month__contains=date.strftime(last_month, '%Y-%m'))
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['wallets'] = Wallet.objects.filter(user=request.user)
            context['budgets'] = Budget.objects.filter(user=request.user,
                                                    month__contains=date.strftime(date.today(), '%Y-%m'))
            context['current_tab'] = 'budgets'
            return render(request, 'pynny/budgets/budgets.html', context=context)

