import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck, SearchCheck } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { ApiRequestError } from '../services/api';
import { Alert, Field } from '../components/ui';

const schema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { user, login, loading } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: string } };
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  if (!loading && user) return <Navigate to={location.state?.from ?? '/'} replace />;

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      await login(values.email, values.password);
      toast('success', 'Signed in successfully.');
      navigate(location.state?.from ?? '/', { replace: true });
    } catch (err) {
      const msg =
        err instanceof ApiRequestError
          ? err.error.message
          : 'Unable to sign in. Please try again.';
      setServerError(msg);
      toast('error', msg);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-navy-950 via-navy-900 to-navy-950 p-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-600/20">
            <SearchCheck className="h-8 w-8 text-sky-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Missing Person Identification System</h1>
          <p className="mt-2 text-sm text-slate-400">
            Authorized investigators and rescue teams only. All access is audit-logged.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="card space-y-4" noValidate>
          {serverError && <Alert kind="error" title="Sign-in failed">{serverError}</Alert>}

          <Field label="Email address" error={errors.email?.message} required>
            <input
              {...register('email')}
              type="email"
              className="input"
              autoComplete="username"
              placeholder="you@agency.gov"
              aria-invalid={!!errors.email}
            />
          </Field>

          <Field label="Password" error={errors.password?.message} required>
            <input
              {...register('password')}
              type="password"
              className="input"
              autoComplete="current-password"
              aria-invalid={!!errors.password}
            />
          </Field>

          <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="flex items-start gap-2 text-xs text-slate-400">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            Public sign-up is disabled. Accounts are created by administrators. Facial-search
            capabilities are never available to anonymous visitors.
          </p>
        </form>
      </div>
    </div>
  );
}
