#!/usr/bin/env python3
'''
File: transaction_views.py
Author: Zachary King

Implements the views/handlers for Transaction-related requetss
'''

from datetime import date, datetime
from django.shortcuts import render, redirect, reverse
from django.contrib.auth.decorators import login_required
import decimal

from . import savings_views
from ..models import Transaction, BudgetCategory, Wallet, Budget, Savings


@login_required(login_url='/pynny/login')
def transactions(request):
    '''View transactions for a user'''
    data = dict()
    data['current_tab'] = 'transactions'

    if request.method == 'GET':
        data['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
        data['categories'] = BudgetCategory.objects.filter(user=request.user)
        data['wallets'] = Wallet.objects.filter(user=request.user)
        data['default_date'] = date.strftime(date.today(), '%Y-%m-%d')
        data['savings'] = Savings.objects.filter(user=request.user, completed=False)
        return render(request, 'pynny/transactions/transactions.html', context=data)
    # POST = create a new Transaction
    elif request.method == 'POST':
        # Get the form data from the request
        _category = request.POST.get('category', None)
        _saving = request.POST.get('saving', None)

        if _category is None and _saving is None:
            data['alerts'] = {'errors': ['<strong>Oh Snap!</strong> Your transaction must either be categorized or put towards a saving']}
            data['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
            data['categories'] = BudgetCategory.objects.filter(user=request.user)
            data['wallets'] = Wallet.objects.filter(user=request.user)
            data['default_date'] = date.strftime(date.today(), '%Y-%m-%d')
            data['savings'] = Savings.objects.filter(user=request.user, completed=False)
            return render(request, 'pynny/transactions/transactions.html', context=data)

        try:
            _category = BudgetCategory.objects.get(id=_category) if _category != 'none' else None
        except BudgetCategory.DoesNotExist:
            pass

        try:
            _saving = Savings.objects.get(id=_saving) if _saving != 'none' else None
        except Savings.DoesNotExist:
            pass

        _wallet = int(request.POST['wallet'])
        _amount = float(request.POST['amount'])
        _description = request.POST['description']
        _created_time = request.POST['created_time'] # %Y-%m-%d date
        _created_time = datetime.strptime(_created_time, '%Y-%m-%d').date()

        wallet = Wallet.objects.get(id=_wallet)

        # Create the new Transaction
        if _saving is None:
            Transaction(category=_category, wallet=wallet, amount=_amount, description=_description, created_time=_created_time, user=request.user).save()
        else:
            Transaction(saving=_saving, wallet=wallet, amount=_amount, description=_description, created_time=_created_time, user=request.user).save()

        # Update the balance of appropriate budgets
        amount = abs(_amount)
        data['alerts'] = {'success': [], 'errors': []}
        if _saving is None:
            budgets = Budget.objects.filter(category=_category)

            for budget in budgets:
                budget.balance += decimal.Decimal(amount)
                budget.save()

            # Update the wallet balance
            if _category.is_income:
                wallet.balance += decimal.Decimal(_amount)
            else:
                wallet.balance -= decimal.Decimal(_amount)
            wallet.save()
        else:
            # Update the wallet balance
            wallet.balance -= decimal.Decimal(_amount)
            wallet.save()

            # Update the saving
            _saving.balance += decimal.Decimal(_amount)
            _saving.save()
            if _saving.goal <= _saving.balance:
                savings_views.complete_saving(_saving)
                data['alerts']['success'].append('<strong>Congratulations!</strong> You met your Savings goal for "{}"'.format(_saving.name))
                data['alerts']['success'].append('<strong>Done!</strong> Saving updated successfully')

        # Render the transactions
        data['alerts']['success'].append('<strong>Done!</strong> New Transaction recorded successfully!')
        data['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
        data['categories'] = BudgetCategory.objects.filter(user=request.user)
        data['wallets'] = Wallet.objects.filter(user=request.user)
        data['savings'] = Savings.objects.filter(user=request.user, completed=False)
        return render(request, 'pynny/transactions/transactions.html', context=data, status=201)


@login_required(login_url='/pynny/login')
def new_transaction(request):
    '''View for creating a new transaction'''
    data = {}
    data['current_tab'] = 'transactions'
    data['categories'] = BudgetCategory.objects.filter(user=request.user)
    data['wallets'] = Wallet.objects.filter(user=request.user)

    # Check if they have any categories or wallets first
    if not data['categories']:
        data = {
            'alerts': {
                'errors': [
                    '<strong>Oy!</strong> You don\'t have any Categories yet! You need to create a Category before you can record a Transaction!'
                ]
            },
        }
        data['current_tab'] = 'categories'
        return render(request, 'pynny/categories/new_category.html', context=data)

    if not data['wallets']:
        data = {
            'alerts': {
                'errors': [
                    '<strong>Oy!</strong> You don\'t have any Wallets yet! You need to create a Wallet before you can record a Transaction!'
                ]
            },
        }
        data['current_tab'] = 'wallets'
        return render(request, 'pynny/wallets/new_wallet.html', context=data)

    # They have a wallet and category so continue
    data['default_date'] = date.strftime(date.today(), '%Y-%m-%d')
    data['savings'] = Savings.objects.filter(user=request.user, completed=False)
    return render(request, 'pynny/transactions/new_transaction.html', context=data)


@login_required(login_url='/pynny/login')
def one_transaction(request, transaction_id):
    '''View for a single Transaction'''
    data = {}
    data['current_tab'] = 'transactions'

    # Check if transaction is owned by user
    try:
        transaction = Transaction.objects.get(id=transaction_id)
    except Transaction.DoesNotExist:
        # DNE
        data['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
        data['savings'] = Savings.objects.filter(user=request.user, completed=False)
        data['alerts'] = {'errors': ['<strong>Oh snap!</strong> That Transaction does not exist.']}
        return render(request, 'pynny/transactions/transactions.html', context=data, status=404)

    if transaction.user != request.user:
        data['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
        data['alerts'] = {'errors': ['<strong>Oh snap!</strong> That Transaction does not exist.']}
        data['savings'] = Savings.objects.filter(user=request.user, completed=False)
        return render(request, 'pynny/transactions/transactions.html', context=data, status=403)

    if request.method == "POST":
        # What kind of POST was this?
        action = request.POST['action'].lower()
        if action == 'delete':
            # Update the balance of appropriate budgets
            undo_transaction(transaction)

            # Delete the Transaction
            transaction.delete()

            # And return them to the Transactions page
            data['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
            data['categories'] = BudgetCategory.objects.filter(user=request.user)
            data['wallets'] = Wallet.objects.filter(user=request.user)
            data['alerts'] = {'info': ['<strong>Done!</strong> Transaction was deleted successfully']}
            data['savings'] = Savings.objects.filter(user=request.user, completed=False)
            return render(request, 'pynny/transactions/transactions.html', context=data)
        elif action == 'edit':
            # Render the edit_transaction view
            data['transaction'] = transaction
            data['categories'] = BudgetCategory.objects.filter(user=request.user)
            data['wallets'] = Wallet.objects.filter(user=request.user)
            data['savings'] = Savings.objects.filter(user=request.user, completed=False)
            return render(request, 'pynny/transactions/edit_transaction.html', context=data)
        elif action == 'edit_complete':
            # Get the form data from the request
            _category = int(request.POST['category'])
            _wallet = int(request.POST['wallet'])
            _amount = float(request.POST['amount'])
            _description = request.POST['description']
            _created_time = request.POST['created_time'] # %Y-%m-%d date
            _created_time = datetime.strptime(_created_time, '%Y-%m-%d').date()

            new_category = BudgetCategory.objects.get(id=_category)

            # Undo the last version of the transaction
            # print('balance before undo: ' + str(transaction.wallet.balance))
            undo_transaction(transaction)
            # print('balance after undo: ' + str(transaction.wallet.balance))

            # Now carry out the effects of the revised transaction
            # Update the balance of appropriate budgets
            budgets = Budget.objects.filter(category=new_category)
            amount = abs(_amount)
            for budget in budgets:
                budget.balance += decimal.Decimal(amount)
                budget.save()

            # Update the wallet balance
            new_wallet = Wallet.objects.get(id=_wallet)
            # print('balance before update: ' + str(new_wallet.balance))
            if new_category.is_income:
                new_wallet.balance += decimal.Decimal(_amount)
            else:
                new_wallet.balance -= decimal.Decimal(_amount)
            new_wallet.save()
            # print('balance after update: ' + str(new_wallet.balance))

            # And update the transaction itself
            transaction.category = new_category
            transaction.wallet = new_wallet
            transaction.amount = _amount
            transaction.description = _description
            transaction.created_time = _created_time
            transaction.save()

            data['alerts'] = {'success': ['<strong>Done!</strong> Transaction updated successfully!']}
            data['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
            data['categories'] = BudgetCategory.objects.filter(user=request.user)
            data['wallets'] = Wallet.objects.filter(user=request.user)
            data['savings'] = Savings.objects.filter(user=request.user, completed=False)
            return render(request, 'pynny/transactions/transactions.html', context=data)
    elif request.method == 'GET':
        # Show the specific Transaction data
        data['transaction'] = transaction
        data['categories'] = BudgetCategory.objects.filter(user=request.user)
        data['wallets'] = Wallet.objects.filter(user=request.user)
        data['savings'] = Savings.objects.filter(user=request.user, completed=False)
        return render(request, 'pynny/transactions/one_transaction.html', context=data)


def undo_transaction(trans):
    """Reverts the effects of a Transaction on budgets and its wallet"""
    amount = trans.amount

    # Category or Saving?
    if trans.saving:
        trans.saving.balance -= amount
        trans.saving.completed = trans.saving.goal <= trans.saving.balance
        trans.saving.save()

        trans.wallet.balance += amount
        trans.wallet.save()
    else:
        # Replace the money in the category
        for budget in Budget.objects.filter(category=trans.category):
            budget.balance -= amount
            budget.save()

        # Replace the money in the wallet
        if trans.category.is_income:
            trans.wallet.balance -= trans.amount
        else:
            trans.wallet.balance += trans.amount
        trans.wallet.save()
