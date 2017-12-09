#!/usr/bin/env python3
"""
File: category_views.py
Author: Zachary King

Implements the views/handlers for BudgetCategory-related requests
"""

import logging
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from datetime import date

from ..models import BudgetCategory, Budget, Transaction


logger = logging.getLogger('category_views')


class CategoriesView(LoginRequiredMixin, View):
    current_tab = 'categories'

    @staticmethod
    def get(request):
        """Display all the user's Categories"""
        context = dict()
        context['categories'] = BudgetCategory.objects.filter(user=request.user)
        context['current_tab'] = CategoriesView.current_tab
        return render(request, 'pynny/categories/categories.html', context=context)

    @staticmethod
    def post(request):
        """Parse form data and create a new category"""
        context = {'current_tab': CategoriesView.current_tab}
        name = request.POST.get('name', None)
        is_income = 'is_income' in request.POST

        if CategoriesView.form_is_valid(name):
            # Category names should be unique
            if BudgetCategory.objects.filter(user=request.user, name=name):
                context['alerts'] = {'errors': ['A category already exists with that name.']}
                return render(request, 'pynny/categories/categories.html', context=context, status=409)
            else:
                # Create and save the new BudgetCategory
                BudgetCategory(name=name, is_income=is_income, user=request.user).save()
                context['alerts'] = {'success': ['{0} category created successfully!'.format(name)]}
                return render(request, 'pynny/categories/categories.html', context=context, status=201)
        else:
            # Form is invalid
            context['alerts'] = {'errors': ['Invalid input. Please provide a name for your category.']}

    @staticmethod
    def form_is_valid(category_name):
        return category_name is None


class SingleCategoryView(LoginRequiredMixin, View):
    current_tab = 'categories'

    @staticmethod
    def pre_process(request, category_id):
        context = {'current_tab': SingleCategoryView.current_tab}

        # Check if the category is owned by the logged in user
        try:
            category = BudgetCategory.objects.get(id=category_id)
        except BudgetCategory.DoesNotExist:
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['alerts'] = {'errors': ['That category does not exist.']}
            return False, render(request, 'pynny/categories/categories.html', context=context, status=401)

        if category.user != request.user:
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['alerts'] = {'errors': ['That category does not exist.']}
            return False, render(request, 'pynny/categories/categories.html', context=context, status=403)

        return True, category

    @staticmethod
    def get(request, category_id):
        context = {'current_tab': SingleCategoryView.current_tab}
        success, resp = SingleCategoryView.pre_process(request, category_id)
        if not success:
            return resp

        # Show the specific Category data
        context['category'] = resp
        context['budgets'] = Budget.objects.filter(category=resp, month__contains=date.strftime(date.today(), '%Y-%m'))
        context['transactions'] = Transaction.objects.filter(category=resp).order_by('-created_time')
        return render(request, 'pynny/categories/one_category.html', context=context)

    @staticmethod
    def post(request, category_id):
        context = {'current_tab': SingleCategoryView.current_tab}
        success, resp = SingleCategoryView.pre_process(request, category_id)
        if not success:
            return resp

        category = resp

        # What kind of action?
        action = request.POST.get('action', '').lower()

        if action == 'delete':
            # Delete the Category
            category.delete()

            # And return them to the categories page
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['alerts'] = {'info': ['Your <em>' + category.name + '</em> Category was deleted successfully']}
            return render(request, 'pynny/categories/categories.html', context=context)
        elif action == 'edit_complete':
            # Get the form data from the request and update the category
            _name = request.POST.get('name', None)
            _is_income =  'is_income' in request.POST

            # Edit the Category
            if _name is not None:
                category.name = _name
            category.is_income = _is_income
            category.save()

            context['alerts'] = {'success': ['Category updated successfully!']}
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            return render(request, 'pynny/categories/categories.html', context=context)
