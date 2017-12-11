#!/usr/bin/env python3
"""
File: budget_views.py
Author: Zachary King

Implements the views/handlers for Budget-related requests
"""

from django.views import View
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import date
import decimal

from ..models import Budget, BudgetCategory, Wallet, Transaction


class RenewBudgetView(LoginRequiredMixin, View):
    def get(self, request):
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
                renewed.add(budget.buddet_id)
            return BudgetsView.as_view()(request)


class BudgetsView(LoginRequiredMixin, View):
    current_tab = 'budgets'

    @staticmethod
    def get(request):
        """Get a User's Budgets"""
        data = dict()
        data['current_tab'] = BudgetsView.current_tab

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
            data = {'alerts': {'errors': ['A budget already exists for that wallet and category for this month.']}}

            data['budgets'] = Budget.objects.filter(user=request.user,
                                                    month__contains=date.strftime(date.today(), '%Y-%m'))
            today = date.today()
            last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
            data['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                               month__contains=date.strftime(last_month, '%Y-%m'))
            data['categories'] = BudgetCategory.objects.filter(user=request.user)
            data['wallets'] = Wallet.objects.filter(user=request.user)

            return render(request, 'pynny/budgets/budgets.html', context=data)

        # Create the new Budget
        try:
            latest_budget = Budget.objects.latest('budget_id')
        except Budget.DoesNotExist:
            latest_budget = None

        new_id = latest_budget.budget_id + 1 if latest_budget is not None else 0
        Budget(category=category, wallet=wallet, goal=_goal, balance=_start_balance, user=request.user,
               budget_id=new_id).save()
        data = {'alerts': {'success': ['New budget created successfully!']}}
        data['budgets'] = Budget.objects.filter(user=request.user, month__contains=date.strftime(date.today(), '%Y-%m'))
        today = date.today()
        last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
        data['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                           month__contains=date.strftime(last_month, '%Y-%m'))
        data['categories'] = BudgetCategory.objects.filter(user=request.user)
        data['wallets'] = Wallet.objects.filter(user=request.user)
        data['current_tab'] = BudgetsView.current_tab
        return render(request, 'pynny/budgets/budgets.html', context=data, status=201)


class SingleBudgetView(LoginRequiredMixin, View):
    current_tab = 'budgets'

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
            context['alerts'] = {'errors': ['That Budget does not exist.']}
            context['current_tab'] = SingleBudgetView.current_tab
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
                'errors': ['That budget does not exist.']}
            context['current_tab'] = SingleBudgetView.current_tab
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
        context['current_tab'] = SingleBudgetView.current_tab
        return render(request, 'pynny/budgets/one_budget.html', context=context)

    @staticmethod
    def post(request, budget_id):
        successful, failed_resp = SingleBudgetView.pre_process(request, budget_id)
        if not successful:
            return failed_resp

        budget = Budget.objects.get(id=budget_id)
        context = dict()
        context['current_tab'] = SingleBudgetView.current_tab

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
            context['alerts'] = {'success': ['Budget deleted successfully.']}
            return render(request, 'pynny/budgets/budgets.html', context=context)
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

            context['alerts'] = {'success': ['Budget updated successfully!']}
            today = date.today()
            last_month = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
            context['last_month_budgets'] = Budget.objects.filter(user=request.user,
                                                                  month__contains=date.strftime(last_month, '%Y-%m'))
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['wallets'] = Wallet.objects.filter(user=request.user)
            context['budgets'] = Budget.objects.filter(user=request.user,
                                                       month__contains=date.strftime(date.today(), '%Y-%m'))
            return render(request, 'pynny/budgets/budgets.html', context=context)

