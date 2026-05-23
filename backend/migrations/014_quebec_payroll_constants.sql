-- Align Quebec payroll constants with TP-1015.G-V 2025 and mark QC as supported.
-- Existing installs may have the original defensive seed that documented QC as unsupported.

UPDATE payroll_constants
SET
    prov_brackets = '[{"min":0,"max":53255,"rate":0.14},{"min":53255,"max":106495,"rate":0.19},{"min":106495,"max":129590,"rate":0.24},{"min":129590,"max":null,"rate":0.2575}]',
    prov_surtax = '{"source":"Revenu Quebec TP-1015.G-V 2025-01","basic_personal_amount":18571}'
WHERE tax_year = 2025
  AND province = 'QC';
