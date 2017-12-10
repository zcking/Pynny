#!/usr/bin/env python3
"""
File: transaction_views.py
Author: Zachary King

Implements the views/handlers for Transaction-related requests
"""

from datetime import date, datetime
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
import decimal

from . import savings_views
from ..models import Transaction, BudgetCategory, Wallet, Budget, Savings


class TransactionsView(LoginRequiredMixin, View):
    current_tab = 'transactions'

    @staticmethod
    def get(request):
        """Get the user's transactions"""
        context = {
            'current_tab': TransactionsView.current_tab,
            'transactions': Transaction.objects.filter(user=request.user).order_by('-created_time'),
            'categories': BudgetCategory.objects.filter(user=request.user),
            'wallets': Wallet.objects.filter(user=request.user),
            'default_date': date.strftime(date.today(), '%Y-%m-%d'),
            'savings': Savings.objects.filter(user=request.user, completed=False)
        }
        return render(request, 'pynny/transactions/transactions.html', context=context)

    @staticmethod
    def fill_default_context(request, context):
        if not context:
            context = dict()
        context['current_tab'] = TransactionsView.current_tab
        context['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
        context['categories'] = BudgetCategory.objects.filter(user=request.user)
        context['wallets'] = Wallet.objects.filter(user=request.user)
        context['default_date'] = date.strftime(date.today(), '%Y-%m-%d')
        context['savings'] = Savings.objects.filter(user=request.user, completed=False)
        return context

    @staticmethod
    def form_is_valid(request):
        context = {'current_tab': TransactionsView.current_tab}
        _category = request.POST.get('category', None)
        _saving = request.POST.get('saving', None)

        if _category is None and _saving is None:
            context = TransactionsView.fill_default_context(request, context)
            context['alerts'] = {'errors': ['Your transaction must either be categorized or put towards a saving.']}
            return False, render(request, 'pynny/transactions/transactions.html', context=context)

        try:
            _category = BudgetCategory.objects.get(id=_category) if _category.lower() != 'none' else None
        except BudgetCategory.DoesNotExist:
            pass

        try:
            _saving = Savings.objects.get(id=_saving) if _saving.lower() != 'none' else None
        except Savings.DoesNotExist:
            pass

        _wallet = request.POST.get('wallet', 'N/A')
        try:
            _wallet = int(_wallet)
        except ValueError:
            context = TransactionsView.fill_default_context(request, context)
            context['alerts'] = {'errors': ['Invalid wallet selected.']}
            return False, render(request, 'pynny/transactions/transactions.html', context=context, status=400)

        _amount = request.POST.get('amount', 'N/A')
        try:
            _amount = float(_amount)
        except ValueError:
            context = TransactionsView.fill_default_context(request, context)
            context['alerts'] = {'errors': ['Invalid amount given for your transaction. Amount must be numeric.']}
            return False, render(request, 'pynny/transactions/transactions.html', context=context, status=400)

        _description = request.POST.get('description', '')
        _created_time = request.POST.get('created_time', datetime.strftime(datetime.today(), '%Y-%m-%d'))
        _created_time = datetime.strptime(_created_time, '%Y-%m-%d').date()

        try:
            wallet = Wallet.objects.get(id=_wallet)
        except Wallet.DoesNotExist:
            context = TransactionsView.fill_default_context(request, context)
            context['alerts'] = {'errors': ['Invalid wallet selected. That wallet does not exist.']}
            return False, render(request, 'pynny/transactions/transactions.html', context=context, status=400)

        if wallet.user != request.user:
            context = TransactionsView.fill_default_context(request, context)
            context['alerts'] = {'errors': ['Invalid wallet selected. That wallet does not exist.']}
            return False, render(request, 'pynny/transactions/transactions.html', context=context, status=400)

        # Create the new Transaction
        if _saving is None:
            return True, Transaction(category=_category, wallet=wallet, amount=_amount, description=_description,
                                     created_time=_created_time, user=request.user)
        else:
            return True, Transaction(saving=_saving, wallet=wallet, amount=_amount, description=_description,
                                     created_time=_created_time, user=request.user)

    @staticmethod
    def post(request):
        """Parse form-data and create a new transaction"""
        context = {'current_tab': TransactionsView.current_tab}
        success, resp = TransactionsView.form_is_valid(request)
        if not success:
            return resp

        transaction = resp
        transaction.save()
        _saving = transaction.saving
        _category = transaction.category
        _amount = transaction.amount
        wallet = transaction.wallet

        # Update the balance of appropriate budgets
        amount = abs(transaction.amount)
        context['alerts'] = {'success': [], 'errors': []}
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

        # Render the transactions
        context['alerts'] = {'success': ['New transaction recorded successfully!']}
        context['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
        context['categories'] = BudgetCategory.objects.filter(user=request.user)
        context['wallets'] = Wallet.objects.filter(user=request.user)
        context['savings'] = Savings.objects.filter(user=request.user, completed=False)
        return render(request, 'pynny/transactions/transactions.html', context=context, status=201)


class SingleTransactionView(LoginRequiredMixin, View):
    """Handles requests to single transaction resources"""
    current_tab = 'transactions'

    @staticmethod
    def pre_process(request, transaction_id):
        """Validate the transaction exists and is owned by the user"""
        context = {'current_tab': SingleTransactionView.current_tab}
        try:
            transaction = Transaction.objects.get(id=transaction_id)
        except Transaction.DoesNotExist:
            # DNE
            context['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
            context['savings'] = Savings.objects.filter(user=request.user, completed=False)
            context['alerts'] = {'errors': ['That transaction does not exist.']}
            return False, render(request, 'pynny/transactions/transactions.html', context=context, status=404)

        if transaction.user != request.user:
            context['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
            context['alerts'] = {'errors': ['That transaction does not exist.']}
            context['savings'] = Savings.objects.filter(user=request.user, completed=False)
            return False, render(request, 'pynny/transactions/transactions.html', context=context, status=403)

        return True, transaction

    @staticmethod
    def get(request, transaction_id):
        """Get the single transaction"""
        context = {'current_tab': SingleTransactionView.current_tab}
        success, resp = SingleTransactionView.pre_process(request, transaction_id)
        if not success:
            return resp
        transaction = resp

        # Show the specific Transaction data
        context['transaction'] = transaction
        context['categories'] = BudgetCategory.objects.filter(user=request.user)
        context['wallets'] = Wallet.objects.filter(user=request.user)
        context['savings'] = Savings.objects.filter(user=request.user, completed=False)
        return render(request, 'pynny/transactions/one_transaction.html', context=context)

    @staticmethod
    def post(request, transaction_id):
        """Parse form-data and update the transaction"""
        context = {'current_tab': SingleTransactionView.current_tab}
        success, resp = SingleTransactionView.pre_process(request, transaction_id)
        if not success:
            return resp
        transaction = resp

        action = request.POST.get('action', '').lower()
        if action == 'delete':
            # Update the balance of appropriate budgets
            undo_transaction(transaction)

            # Delete the Transaction
            transaction.delete()

            # And return them to the Transactions page
            context['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['wallets'] = Wallet.objects.filter(user=request.user)
            context['alerts'] = {'info': ['Transaction was deleted successfully']}
            context['savings'] = Savings.objects.filter(user=request.user, completed=False)
            return render(request, 'pynny/transactions/transactions.html', context=context)
        elif action == 'edit_complete':
            # Get the form data from the request
            _category_id = request.POST.get('category', None)
            _saving_id = request.POST.get('saving', None)

            # Either a category or a saving must be linked to the transaction
            if _category_id is None and _saving_id is None:
                context['alerts'] = {'errors': ['You must select either a category or a saving for the transaction.']}
                context['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
                context['categories'] = BudgetCategory.objects.filter(user=request.user)
                context['wallets'] = Wallet.objects.filter(user=request.user)
                context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                return render(request, 'pynny/transactions/transactions.html', context=context)

            if _category_id is not None and _category_id != 'none':
                try:
                    _category_id = int(_category_id)
                except (ValueError, TypeError):
                    context['alerts'] = {'errors': ['Invalid category selected.']}
                    context['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
                    context['categories'] = BudgetCategory.objects.filter(user=request.user)
                    context['wallets'] = Wallet.objects.filter(user=request.user)
                    context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                    return render(request, 'pynny/transactions/transactions.html', context=context)
            if _saving_id is not None and _saving_id != 'none':
                try:
                    _saving_id = int(_saving_id)
                except (ValueError, TypeError):
                    context['alerts'] = {'errors': ['Invalid saving selected.']}
                    context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                        '-created_time')
                    context['categories'] = BudgetCategory.objects.filter(user=request.user)
                    context['wallets'] = Wallet.objects.filter(user=request.user)
                    context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                    return render(request, 'pynny/transactions/transactions.html', context=context)

            if _category_id == 'none' and _saving_id == 'none':
                context['alerts'] = {'errors': ['You must attach your transaction to either a category or saving.']}
                context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                    '-created_time')
                context['categories'] = BudgetCategory.objects.filter(user=request.user)
                context['wallets'] = Wallet.objects.filter(user=request.user)
                context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                return render(request, 'pynny/transactions/transactions.html', context=context)

            _wallet_id = request.POST.get('wallet', None)
            if _wallet_id is None or not str(_wallet_id).isdigit():
                context['alerts'] = {'errors': ['You must specify a wallet for the transaction.']}
                context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                    '-created_time')
                context['categories'] = BudgetCategory.objects.filter(user=request.user)
                context['wallets'] = Wallet.objects.filter(user=request.user)
                context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                return render(request, 'pynny/transactions/transactions.html', context=context)
            else:
                _wallet_id = int(request.POST['wallet'])

            try:
                _amount = float(request.POST.get('amount', '0.0'))
            except ValueError:
                context['alerts'] = {'errors': ['Invalid amount given. Amount must be numeric.']}
                context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                    '-created_time')
                context['categories'] = BudgetCategory.objects.filter(user=request.user)
                context['wallets'] = Wallet.objects.filter(user=request.user)
                context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                return render(request, 'pynny/transactions/transactions.html', context=context)

            _description = request.POST.get('description', '')
            _created_time = request.POST.get('created_time', datetime.strftime(datetime.today(), '%Y-%m-%d'))
            _created_time = datetime.strptime(_created_time, '%Y-%m-%d').date()

            if _category_id is not None and _category_id != 'none':
                try:
                    new_category = BudgetCategory.objects.get(id=_category_id) if _category_id is not None else None
                except BudgetCategory.DoesNotExist:
                    context['alerts'] = {'errors': ['Invalid category selected. That category does not exist.']}
                    context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                        '-created_time')
                    context['categories'] = BudgetCategory.objects.filter(user=request.user)
                    context['wallets'] = Wallet.objects.filter(user=request.user)
                    context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                    return render(request, 'pynny/transactions/transactions.html', context=context, status=400)

                if new_category.user != request.user:
                    context['alerts'] = {'errors': ['Invalid category selected. That category does not exist.']}
                    context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                        '-created_time')
                    context['categories'] = BudgetCategory.objects.filter(user=request.user)
                    context['wallets'] = Wallet.objects.filter(user=request.user)
                    context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                    return render(request, 'pynny/transactions/transactions.html', context=context, status=400)
            else:
                new_category = None

            if _saving_id is not None and _saving_id != 'none':
                try:
                    new_saving = Savings.objects.get(id=_saving_id) if _saving_id is not None else None
                except Savings.DoesNotExist:
                    context['alerts'] = {'errors': ['Invalid saving selected. That saving does not exist.']}
                    context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                        '-created_time')
                    context['categories'] = BudgetCategory.objects.filter(user=request.user)
                    context['wallets'] = Wallet.objects.filter(user=request.user)
                    context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                    return render(request, 'pynny/transactions/transactions.html', context=context, status=400)

                if new_saving.user != request.user:
                    context['alerts'] = {'errors': ['Invalid saving selected. That saving does not exist.']}
                    context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                        '-created_time')
                    context['categories'] = BudgetCategory.objects.filter(user=request.user)
                    context['wallets'] = Wallet.objects.filter(user=request.user)
                    context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                    return render(request, 'pynny/transactions/transactions.html', context=context)
            else:
                new_saving = None

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
            try:
                new_wallet = Wallet.objects.get(id=_wallet_id)
            except Wallet.DoesNotExist:
                context['alerts'] = {'errors': ['Invalid wallet selected. That wallet does not exist.']}
                context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                    '-created_time')
                context['categories'] = BudgetCategory.objects.filter(user=request.user)
                context['wallets'] = Wallet.objects.filter(user=request.user)
                context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                return render(request, 'pynny/transactions/transactions.html', context=context, status=400)

            if new_wallet.user != request.user:
                context['alerts'] = {'errors': ['Invalid wallet selected. That wallet does not exist.']}
                context['transactions'] = Transaction.objects.filter(user=request.user).order_by(
                    '-created_time')
                context['categories'] = BudgetCategory.objects.filter(user=request.user)
                context['wallets'] = Wallet.objects.filter(user=request.user)
                context['savings'] = Savings.objects.filter(user=request.user, completed=False)
                return render(request, 'pynny/transactions/transactions.html', context=context, status=400)

            if new_category is not None:
                if new_category.is_income:
                    new_wallet.balance += decimal.Decimal(_amount)
                else:
                    new_wallet.balance -= decimal.Decimal(_amount)
                new_wallet.save()
            elif new_saving is not None:
                new_wallet.balance -= decimal.Decimal(_amount)
                new_saving.balance += decimal.Decimal(_amount)
                new_wallet.save()
                new_saving.save()

            # And update the transaction itself
            transaction.category = new_category if new_category is not None else None
            transaction.saving = new_saving if new_saving is not None else None
            transaction.wallet = new_wallet
            transaction.amount = _amount
            transaction.description = _description
            transaction.created_time = _created_time
            transaction.save()

            context['alerts'] = {'success': ['Transaction updated successfully!']}
            context['transactions'] = Transaction.objects.filter(user=request.user).order_by('-created_time')
            context['categories'] = BudgetCategory.objects.filter(user=request.user)
            context['wallets'] = Wallet.objects.filter(user=request.user)
            context['savings'] = Savings.objects.filter(user=request.user, completed=False)
            return render(request, 'pynny/transactions/transactions.html', context=context)


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
