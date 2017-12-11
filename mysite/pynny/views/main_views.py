#!/usr/bin/python3
"""
File: main_views.py
Author: Zachary King

Implements the main site views (endpoint handlers) for the Pynny web app.
"""

from django.shortcuts import render
from django.contrib.auth import logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required

from datetime import date, datetime
from django.utils import timezone
import random

from ..models import Budget, Transaction, BudgetCategory, Notification


@login_required(login_url='/pynny/login')
def index(request):
    """The Home page for Pynny"""

    # User is logged in, so retrieve their data and
    # show them their home page, displaying a dashboard
    data = {}
    budgets = Budget.objects.filter(user=request.user, month__contains=date.strftime(date.today(), '%Y-%m'))
    colors = ['#ff4444', '#ffbb33', '#00C851', '#33b5e5', '#aa66cc', '#a1887f']
    random.shuffle(colors)
    color_index = 0
    data['budgets'] = budgets
    data['categories'] = BudgetCategory.objects.filter(user=request.user)
    data['transactions'] = Transaction.objects.filter(user=request.user, created_time__year=timezone.now().year, created_time__month=timezone.now().month)
    data['budget_categories'] = []
    data['budget_colors'] = []
    data['budget_goal_data'] = []
    data['budget_balance_data'] = []
    data['transactions_per_category_data'] = []
    data['transactions_per_category_colors'] = []
    data['transactions_per_category_labels'] = []
    data['current_month'] = date.today().strftime('%B, %Y')

    for budget in budgets:
        data['budget_categories'].append(budget.category.name)
        data['budget_goal_data'].append(budget.goal)
        data['budget_balance_data'].append(budget.balance)
        data['budget_colors'].append(colors[color_index])
        color_index = (color_index + 1) % len(colors)

    random.shuffle(colors)
    for category in BudgetCategory.objects.filter(user=request.user):
        data['transactions_per_category_labels'].append(category.name)
        data['transactions_per_category_data'].append(len(Transaction.objects.filter(category=category)))
        data['transactions_per_category_colors'].append(colors[color_index])
        color_index = (color_index + 1) % len(colors)

    data['current_tab'] = 'dashboard'
    return render(request, 'pynny/base/dashboard.html', context=data)


@login_required(login_url='/pynny/login')
def logout_view(request):
    '''Handlers user logout requests'''

    # User is logged in, so log them out
    logout(request)

    data = {
        'alerts': {
            'success': ['You have been logged out successfully.']
        }
    }
    return render(request, 'registration/login.html', context=data)


@login_required(login_url='/pynny/login')
def settings_view(request):
    """Handles displaying and updating the logged-in user's settings"""
    data = dict()
    data['current_tab'] = 'settings'
    data['alerts'] = {'success': [], 'errors': [], 'info': [], 'warnings': []}

    if request.method == 'GET':
        return render(request, 'pynny/base/settings.html', context=data)
    elif request.method == 'POST':
        first_name = request.POST.get('first_name', None)
        last_name = request.POST.get('last_name', None)
        email = request.POST.get('email', None)
        username = request.POST.get('username', None)
        old_pass = request.POST.get('old_password', '')
        new_pass = request.POST.get('new_password', None)
        verify_new_pass = request.POST.get('verify_new_password', None)

        has_errors = False

        if authenticate(request, username=request.user.username, password=old_pass):
            if first_name and first_name != request.user.first_name:
                request.user.first_name = first_name

            if last_name and last_name != request.user.last_name:
                request.user.last_name = last_name

            if email and email != request.user.email:
                if len(get_user_model().objects.filter(email=email)) == 0:
                    request.user.email = email
                else:
                    data['alerts']['errors'].append('A user already exists with that email.')
                    has_errors = True

            if username and username != request.user.username:
                if len(get_user_model().objects.filter(username=username)) == 0:
                    request.user.username = username
                else:
                    data['alerts']['errors'].append('A user already exists with that username.')
                    has_errors = True

            if new_pass:
                if verify_new_pass and verify_new_pass == new_pass:
                    request.user.set_password(new_pass)
                elif verify_new_pass:
                    data['alerts']['errors'].append('The new password you entered does match.')
                    has_errors = True

            if not has_errors:
                request.user.save()
                data['alerts']['success'].append('You\'re settings have been updated successfully!')

            return render(request, 'pynny/base/settings.html', context=data)
