import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../../../services/api';
import { useAuth } from '../../../../contexts/AuthContext';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import { Label } from '../../../../components/ui/label';
import { Textarea } from '../../../../components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../../../components/ui/select';

const shopTypes = [
  { value: 'barber', label: 'Barber Shop' },
  { value: 'salon', label: 'Hair Salon' },
  { value: 'doctor', label: 'Doctor/Medical' },
  { value: 'restaurant', label: 'Restaurant' },
  { value: 'spa', label: 'Spa' },
  { value: 'other', label: 'Other' },
];

const formatApiError = (detail: unknown): string => {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((entry) => {
        if (typeof entry === 'string') return entry;
        if (entry && typeof entry === 'object' && 'msg' in entry && typeof entry.msg === 'string') return entry.msg;
        return null;
      })
      .filter((e): e is string => Boolean(e))
      .join(', ');
  }
  if (detail && typeof detail === 'object' && 'msg' in detail && typeof (detail as any).msg === 'string') {
    return (detail as any).msg;
  }
  return 'Registration failed. Please try again.';
};

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mt-2">
      <span className="text-sm font-semibold text-violet-400 uppercase tracking-wider">{children}</span>
      <div className="flex-1 h-px bg-white/10" />
    </div>
  );
}

function FieldGroup({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{children}</div>;
}

function Field({
  id,
  label,
  required,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-sm text-white/70">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </Label>
      {children}
    </div>
  );
}

const inputClass = 'border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-violet-500';

export default function ShopOwnerSignUp() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');

  const [formData, setFormData] = React.useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    shopName: '',
    shop_type: 'barber',
    description: '',
    address: '',
    city: '',
    state: '',
    zip_code: '',
    country: 'United States',
    phone: '',
    shopEmail: '',
    website: '',
    average_service_time: 30,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSelectChange = (name: string, value: string) => {
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);
    try {
      await api.post('/users', {
        username: formData.username,
        email: formData.email,
        password: formData.password,
        role: 'shop_owner',
      });

      // Step 2: Login via AuthContext so isAuthenticated + user state are updated
      await login(formData.username, formData.password);

      await api.post('/shops/', {
        name: formData.shopName,
        shop_type: formData.shop_type,
        description: formData.description,
        address: formData.address,
        city: formData.city,
        state: formData.state,
        zip_code: formData.zip_code,
        country: formData.country,
        phone: formData.phone,
        email: formData.shopEmail || formData.email,
        website: formData.website,
        average_service_time: parseInt(formData.average_service_time.toString()),
      });

      navigate('/dashboard');
    } catch (err: any) {
      setError(formatApiError(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex min-h-screen w-full items-start justify-center px-4 py-10"
      style={{
        background: 'radial-gradient(ellipse at 50% 50%, hsl(270, 50%, 25%), hsl(260, 60%, 8%))',
      }}
    >
      <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-white/[0.06] p-8 backdrop-blur-xl shadow-2xl">
        {/* Header */}
        <div className="mb-8">
          <div className="text-3xl font-bold text-violet-400 mb-1">ZeroQwait</div>
          <h1 className="text-2xl font-bold text-white">Create Your Shop Account</h1>
          <p className="text-sm text-white/50 mt-1">Register your business and start managing queues</p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Account Information */}
          <SectionHeading>Account Information</SectionHeading>

          <FieldGroup>
            <Field id="username" label="Username" required>
              <Input
                id="username"
                name="username"
                required
                autoComplete="username"
                value={formData.username}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
            <Field id="email" label="Email" required>
              <Input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="email"
                value={formData.email}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
          </FieldGroup>

          <FieldGroup>
            <Field id="password" label="Password" required>
              <Input
                id="password"
                name="password"
                type="password"
                required
                autoComplete="new-password"
                value={formData.password}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
            <Field id="confirmPassword" label="Confirm Password" required>
              <Input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                required
                autoComplete="new-password"
                value={formData.confirmPassword}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
          </FieldGroup>

          {/* Business Information */}
          <SectionHeading>Business Information</SectionHeading>

          <FieldGroup>
            <Field id="shopName" label="Shop Name" required>
              <Input
                id="shopName"
                name="shopName"
                required
                value={formData.shopName}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
            <Field id="shop_type" label="Business Type" required>
              <Select
                value={formData.shop_type}
                onValueChange={(v) => handleSelectChange('shop_type', v)}
              >
                <SelectTrigger
                  id="shop_type"
                  className="border-white/10 bg-white/5 text-white focus:ring-violet-500"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {shopTypes.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </FieldGroup>

          <Field id="description" label="Description">
            <Textarea
              id="description"
              name="description"
              rows={2}
              value={formData.description}
              onChange={handleChange}
              className={inputClass + ' resize-none'}
              placeholder="Briefly describe your business..."
            />
          </Field>

          {/* Location */}
          <SectionHeading>Location</SectionHeading>

          <Field id="address" label="Street Address" required>
            <Input
              id="address"
              name="address"
              required
              value={formData.address}
              onChange={handleChange}
              className={inputClass}
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field id="city" label="City" required>
              <Input
                id="city"
                name="city"
                required
                value={formData.city}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
            <Field id="state" label="State/Region" required>
              <Input
                id="state"
                name="state"
                required
                value={formData.state}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
            <Field id="zip_code" label="ZIP Code" required>
              <Input
                id="zip_code"
                name="zip_code"
                required
                value={formData.zip_code}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
          </div>

          {/* Contact */}
          <SectionHeading>Contact Information</SectionHeading>

          <FieldGroup>
            <Field id="phone" label="Phone" required>
              <Input
                id="phone"
                name="phone"
                required
                value={formData.phone}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
            <Field id="shopEmail" label="Business Email (optional)">
              <Input
                id="shopEmail"
                name="shopEmail"
                type="email"
                value={formData.shopEmail}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
          </FieldGroup>

          <FieldGroup>
            <Field id="website" label="Website (optional)">
              <Input
                id="website"
                name="website"
                value={formData.website}
                onChange={handleChange}
                className={inputClass}
                placeholder="https://"
              />
            </Field>
            <Field id="average_service_time" label="Avg. Service Time (min)">
              <Input
                id="average_service_time"
                name="average_service_time"
                type="number"
                min={5}
                max={180}
                value={formData.average_service_time}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
          </FieldGroup>

          <Button
            type="submit"
            disabled={loading}
            className="mt-4 w-full bg-violet-600 hover:bg-violet-500 text-white font-semibold py-3"
          >
            {loading ? 'Creating Account...' : 'Create Shop Account'}
          </Button>

          <p className="text-center text-sm text-white/50">
            Already have an account?{' '}
            <a href="/login" className="text-violet-400 hover:text-violet-300 transition-colors">
              Sign in
            </a>
          </p>
        </form>
      </div>
    </div>
  );
}
