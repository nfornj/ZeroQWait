import unittest

from agents.payroll_calculator import (
    PayPeriodInput,
    PayrollConstants,
    calculate_payslip,
    calculate_provincial_tax,
)


FEDERAL_2025 = [
    {"min": 0, "max": 57375, "rate": 0.15},
    {"min": 57375, "max": 114750, "rate": 0.205},
    {"min": 114750, "max": 177882, "rate": 0.26},
    {"min": 177882, "max": 253414, "rate": 0.29},
    {"min": 253414, "max": None, "rate": 0.33},
]

QUEBEC_2025 = [
    {"min": 0, "max": 53255, "rate": 0.14},
    {"min": 53255, "max": 106495, "rate": 0.19},
    {"min": 106495, "max": 129590, "rate": 0.24},
    {"min": 129590, "max": None, "rate": 0.2575},
]


def _qc_constants() -> PayrollConstants:
    return PayrollConstants(
        tax_year=2025,
        province="QC",
        cpp_rate=0.0595,
        cpp_employee_max=4055.50,
        cpp_basic_exemption=3500.00,
        ei_rate=0.0166,
        ei_employee_max=1049.12,
        ei_insurable_max=63200.00,
        fed_brackets=FEDERAL_2025,
        prov_brackets=QUEBEC_2025,
        prov_surtax={},
    )


class TestPayrollCalculator(unittest.TestCase):
    def test_quebec_provincial_tax_uses_tp1015_claim_credit(self) -> None:
        tax = calculate_provincial_tax(
            gross_period=1600.00,
            cpp_period=87.19,
            ei_period=26.56,
            pay_frequency="biweekly",
            td1_prov_claim=18571.00,
            constants=_qc_constants(),
        )

        self.assertEqual(tax, 108.08)

    def test_quebec_payslip_no_longer_raises(self) -> None:
        result = calculate_payslip(
            PayPeriodInput(
                regular_hours=80,
                hourly_rate=20.00,
                pay_type="hourly",
                pay_frequency="biweekly",
                td1_federal_claim=16129.00,
                td1_prov_claim=18571.00,
            ),
            _qc_constants(),
        )

        self.assertEqual(result.gross_pay, 1600.00)
        self.assertGreater(result.prov_tax, 0)
        self.assertGreater(result.net_pay, 0)


if __name__ == "__main__":
    unittest.main()