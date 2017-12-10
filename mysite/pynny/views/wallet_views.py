#!/usr/bin/env python3
"""
File: wallet_views.py
Author: Zachary King

Implements views/handlers for Wallet-related requests
"""

from django.shortcuts import render
from datetime import date
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from ..models import Wallet, Budget, Transaction


class WalletsView(LoginRequiredMixin, View):
    """Handles requests to the wallets resources"""
    current_tab = 'wallets'

    @staticmethod
    def wallets_with_alerts(request, alerts, status=200):
        context = {
            'current_tab': WalletsView.current_tab,
            'wallets': Wallet.objects.filter(user=request.user),
            'alerts': alerts
        }
        return render(request, 'pynny/wallets/wallets.html', context=context, status=status)

    @staticmethod
    def get(request):
        return WalletsView.wallets_with_alerts(request, {})

    @staticmethod
    def post(request):
        """Parse form-data and create a new Wallet"""
        name = request.POST.get('name', None)
        start_balance = request.POST.get('balance', '0.0')

        if name is None:
            return WalletsView.wallets_with_alerts(
                request,
                {'errors': ['You must give a unique name for your wallet.']},
                status=400
            )
        else:
            if Wallet.objects.filter(user=request.user, name=name):
                return WalletsView.wallets_with_alerts(
                    request,
                    {'errors': ['That name already exists. Please name your wallet uniquely.']},
                    status=400
                )

        try:
            start_balance = float(start_balance)
        except ValueError:
            start_balance = 0.0

        # Create the new Wallet
        Wallet(name=name, balance=start_balance, user=request.user).save()
        return WalletsView.wallets_with_alerts(
            request,
            {'success': ['<em>{0}</em> wallet created successfully.'.format(name)]},
            status=201
        )


class SingleWalletView(LoginRequiredMixin, View):
    """Handles requests to a single wallet resource"""
    current_tab = 'wallets'

    @staticmethod
    def pre_process(request, wallet_id):
        """Validation and checking"""
        try:
            wallet = Wallet.objects.get(id=wallet_id)
        except Wallet.DoesNotExist:
            return False, WalletsView.wallets_with_alerts(
                request,
                {'errors': ['That wallet does not exist.']},
                status=404
            )

        if wallet.user != request.user:
            return False, WalletsView.wallets_with_alerts(
                request,
                {'errors': ['That wallet does not exist.']},
                status=403
            )

        return True, wallet

    @staticmethod
    def get(request, wallet_id):
        """Get the single wallet's data and render it"""
        success, resp = SingleWalletView.pre_process(request, wallet_id)
        if not success:
            return resp
        else:
            wallet = resp
            context = {
                'current_tab': SingleWalletView.current_tab,
                'wallet': wallet,
                'budgets': Budget.objects.filter(wallet=wallet, month__contains=date.strftime(date.today(), '%Y-%m')),
                'transactions': Transaction.objects.filter(wallet=wallet).order_by('-created_time')
            }
            return render(request, 'pynny/wallets/one_wallet.html', context=context)

    @staticmethod
    def post(request, wallet_id):
        success, resp = SingleWalletView.pre_process(request, wallet_id)
        if not success:
            return resp
        else:
            wallet = resp

        # What action?
        action = request.POST.get('action', '').lower()

        if action == 'delete':
            # Delete the wallet
            wallet.delete()

            # And return them to the wallets page
            return WalletsView.wallets_with_alerts(
                request,
                {'success': ['<em>{}</em> wallet deleted successfully.'.format(wallet.name)]}
            )
        elif action == 'edit_complete':
            # Get the form data from the request
            _name = request.POST.get('name', None)
            if _name is None or len(Wallet.objects.filter(user=request.user, name=_name)) > 0:
                return WalletsView.wallets_with_alerts(
                    request,
                    {'errors': ['Please choose a unique, nonempty name for your wallet.']},
                    status=400
                )

            # Edit the Wallet
            wallet.name = _name
            wallet.save()

            return WalletsView.wallets_with_alerts(
                request,
                {'success': ['Wallet updated successfully']}
            )
