from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, Date, Text
from sqlalchemy.orm import relationship
from datetime import datetime, date
from database import Base

class ShopEmployee(Base):
    __tablename__ = "shop_employees"
    
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("platform.users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("platform.users.id"))
    is_active = Column(Boolean, default=True, index=True)
    employee_code = Column(String, nullable=True) # Visible ID for shop use
    
    # Relationships
    shop = relationship("Shop", back_populates="employees")
    user = relationship("User", back_populates="employee_shops", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])
    payroll_profile = relationship(
        "EmployeePayrollProfile",
        back_populates="shop_employee",
        uselist=False,
        cascade="all, delete-orphan",
    )

class EmployeePayrollProfile(Base):
    __tablename__ = "employee_payroll_profiles"

    id               = Column(Integer, primary_key=True, index=True)
    shop_employee_id = Column(Integer, ForeignKey("shop_employees.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    shop_id          = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)

    # compensation
    pay_type         = Column(String(10), nullable=False, default="hourly")   # 'hourly' | 'salary'
    hourly_rate      = Column(Numeric(10, 4), nullable=True)
    annual_salary    = Column(Numeric(12, 2), nullable=True)
    pay_frequency    = Column(String(10), nullable=False, default="biweekly") # weekly/biweekly/semi_monthly/monthly

    # tax identity
    sin_encrypted    = Column(Text, nullable=True)
    sin_last4        = Column(String(4), nullable=True)
    province         = Column(String(2), nullable=False, default="ON")
    td1_federal_claim = Column(Numeric(10, 2), nullable=False, default=16129.00)
    td1_prov_claim   = Column(Numeric(10, 2), nullable=False, default=11865.00)
    additional_tax   = Column(Numeric(10, 2), nullable=False, default=0.00)

    # employment dates
    hire_date        = Column(Date, nullable=False, default=date.today)
    termination_date = Column(Date, nullable=True)

    # YTD accumulators
    ytd_gross        = Column(Numeric(12, 2), nullable=False, default=0.00)
    ytd_cpp          = Column(Numeric(12, 2), nullable=False, default=0.00)
    ytd_ei           = Column(Numeric(12, 2), nullable=False, default=0.00)
    ytd_fed_tax      = Column(Numeric(12, 2), nullable=False, default=0.00)
    ytd_prov_tax     = Column(Numeric(12, 2), nullable=False, default=0.00)
    ytd_tips         = Column(Numeric(12, 2), nullable=False, default=0.00)
    ytd_year         = Column(Integer, nullable=False, default=lambda: datetime.utcnow().year)

    created_at       = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at       = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shop_employee    = relationship("ShopEmployee", back_populates="payroll_profile")

class EmployeeShift(Base):
    __tablename__ = "employee_shifts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("platform.users.id", ondelete="CASCADE"), nullable=False, index=True)
    shop_id = Column(Integer, ForeignKey("platform.shops.id", ondelete="CASCADE"), nullable=False, index=True)
    clock_in = Column(DateTime, default=datetime.utcnow, nullable=False)
    clock_out = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="employee_shifts")
    shop = relationship("Shop")
