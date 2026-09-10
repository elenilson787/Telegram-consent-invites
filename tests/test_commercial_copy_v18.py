import unittest

from local_app_v18 import (
    confirmation_email_message,
    format_account_allowance,
    friendly_plan_name,
    friendly_subscription_status,
)


class CommercialCopyV18Tests(unittest.TestCase):
    def test_trial_plan_is_customer_friendly(self):
        self.assertEqual(friendly_plan_name('trial', 'Teste'), 'Teste gratuito')
        self.assertEqual(friendly_plan_name('pro', 'Pro'), 'Pro')

    def test_subscription_statuses_are_customer_friendly(self):
        self.assertEqual(
            friendly_subscription_status('trialing', True),
            '🟢 Em período de teste',
        )
        self.assertEqual(
            friendly_subscription_status('active', True),
            '🟢 Assinatura ativa',
        )
        self.assertEqual(
            friendly_subscription_status('expired', False),
            '🔴 Assinatura expirada',
        )

    def test_account_allowance_has_correct_portuguese_agreement(self):
        self.assertEqual(format_account_allowance(1, 1), '1 conta cadastrada de 1 permitida')
        self.assertEqual(format_account_allowance(0, 1), '0 contas cadastradas de 1 permitida')
        self.assertEqual(format_account_allowance(1, 3), '1 conta cadastrada de 3 permitidas')
        self.assertEqual(format_account_allowance(3, 3), '3 contas cadastradas de 3 permitidas')

    def test_confirmation_message_tells_user_exact_next_step(self):
        message = confirmation_email_message('cliente@example.com')
        self.assertIn('Verifique no e-mail informado', message)
        self.assertIn('cliente@example.com', message)
        self.assertIn('link de confirmação', message)
        self.assertIn('clique em Entrar', message)


if __name__ == '__main__':
    unittest.main()
