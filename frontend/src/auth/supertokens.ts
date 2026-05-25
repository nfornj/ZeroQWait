import SuperTokens from 'supertokens-auth-react';
import EmailPassword from 'supertokens-auth-react/recipe/emailpassword';
import Session from 'supertokens-auth-react/recipe/session';
import type { RecipeInterface } from 'supertokens-web-js/recipe/emailpassword';
import type { User as SuperTokensUser } from 'supertokens-web-js/types';

const configuredApiUrl = process.env.REACT_APP_API_URL || '/api';

const apiUrl = new URL(configuredApiUrl, window.location.origin);
const apiBasePath = apiUrl.pathname.replace(/\/$/, '') || '/api';
const apiDomain = apiUrl.origin;

function apiPath(path: string): string {
  return `${apiBasePath}${path}`;
}

function formValue(fields: { id: string; value: string }[], id: string, fallback = ''): string {
  return fields.find((field) => field.id === id)?.value?.trim() || fallback;
}

function toSuperTokensUser(user: any): SuperTokensUser {
  const userId = String(user.id);
  const email = user.email || '';
  return {
    id: userId,
    timeJoined: Date.now(),
    isPrimaryUser: true,
    tenantIds: ['public'],
    emails: email ? [email] : [],
    phoneNumbers: [],
    thirdParty: [],
    loginMethods: [
      {
        tenantIds: ['public'],
        timeJoined: Date.now(),
        recipeId: 'emailpassword',
        recipeUserId: userId,
        verified: true,
        email,
      },
    ],
  };
}

async function readJson(response: Response): Promise<any> {
  try {
    return await response.clone().json();
  } catch {
    return {};
  }
}

function storeAccessToken(payload: any): void {
  if (payload?.access_token) {
    localStorage.setItem('token', payload.access_token);
  }
}

async function fetchCurrentUser(accessToken?: string): Promise<any> {
  const response = await fetch(apiPath('/users/me'), {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Unable to load current user');
  }
  return response.json();
}

function withZeroQwaitAuth(originalImplementation: RecipeInterface): RecipeInterface {
  return {
    ...originalImplementation,
    signIn: async (input) => {
      const usernameOrEmail = formValue(input.formFields, 'email');
      const password = formValue(input.formFields, 'password');
      const response = await fetch(apiPath('/auth/login'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: usernameOrEmail, password }),
      });

      const payload = await readJson(response);
      if (response.status === 401) {
        return { status: 'WRONG_CREDENTIALS_ERROR', fetchResponse: response };
      }
      if (!response.ok) {
        return {
          status: 'FIELD_ERROR',
          formFields: [{ id: 'email', error: payload.detail || 'Sign in failed' }],
          fetchResponse: response,
        };
      }

      storeAccessToken(payload);
      const user = await fetchCurrentUser(payload.access_token);
      return { status: 'OK', user: toSuperTokensUser(user), fetchResponse: response };
    },
    signUp: async (input) => {
      const email = formValue(input.formFields, 'email');
      const password = formValue(input.formFields, 'password');
      const username = formValue(input.formFields, 'username', email.split('@')[0]);
      const response = await fetch(apiPath('/auth/register'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password, role: 'shop_owner' }),
      });

      const payload = await readJson(response);
      if (!response.ok) {
        return {
          status: 'FIELD_ERROR',
          formFields: [{ id: response.status === 400 ? 'email' : 'username', error: payload.detail || 'Sign up failed' }],
          fetchResponse: response,
        };
      }

      storeAccessToken(payload);
      const accessToken = payload.access_token;
      const shopName = formValue(input.formFields, 'shopName');
      if (shopName) {
        const shopResponse = await fetch(apiPath('/shops/'), {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify({
            name: shopName,
            shop_type: formValue(input.formFields, 'shop_type', 'barber'),
            description: formValue(input.formFields, 'description'),
            address: formValue(input.formFields, 'address'),
            city: formValue(input.formFields, 'city'),
            state: formValue(input.formFields, 'state'),
            zip_code: formValue(input.formFields, 'zip_code'),
            country: formValue(input.formFields, 'country', 'United States'),
            phone: formValue(input.formFields, 'phone'),
            email: formValue(input.formFields, 'shopEmail', email),
            website: formValue(input.formFields, 'website'),
            average_service_time: Number(formValue(input.formFields, 'average_service_time', '30')) || 30,
          }),
        });

        if (!shopResponse.ok) {
          const shopPayload = await readJson(shopResponse);
          return {
            status: 'FIELD_ERROR',
            formFields: [{ id: 'shopName', error: shopPayload.detail || 'Shop creation failed' }],
            fetchResponse: shopResponse,
          };
        }
      }

      const user = payload.user || (await fetchCurrentUser(accessToken));
      return { status: 'OK', user: toSuperTokensUser(user), fetchResponse: response };
    },
  };
}

SuperTokens.init({
  appInfo: {
    appName: 'ZeroQwait',
    apiDomain,
    apiBasePath: `${apiBasePath}/auth`,
    websiteDomain: window.location.origin,
    websiteBasePath: '/auth',
  },
  recipeList: [
    EmailPassword.init({
      signInAndUpFeature: {
        signInForm: {
          formFields: [
            {
              id: 'email',
              label: 'Email or username',
              placeholder: 'username or email',
            },
          ],
        },
        signUpForm: {
          formFields: [
            { id: 'username', label: 'Username', placeholder: 'your username' },
            { id: 'shopName', label: 'Shop name', placeholder: 'Elite Style Studio' },
            { id: 'shop_type', label: 'Business type', placeholder: 'barber', getDefaultValue: () => 'barber' },
            { id: 'description', label: 'Description', placeholder: 'Briefly describe your business', optional: true },
            { id: 'address', label: 'Street address', placeholder: '123 Main Street' },
            { id: 'city', label: 'City', placeholder: 'Toronto' },
            { id: 'state', label: 'State/region', placeholder: 'ON' },
            { id: 'zip_code', label: 'ZIP code', placeholder: 'M5V 1A1' },
            { id: 'country', label: 'Country', placeholder: 'United States', getDefaultValue: () => 'United States' },
            { id: 'phone', label: 'Phone', placeholder: '+1 555 123 4567' },
            { id: 'shopEmail', label: 'Business email', placeholder: 'frontdesk@example.com', optional: true },
            { id: 'website', label: 'Website', placeholder: 'https://example.com', optional: true },
            { id: 'average_service_time', label: 'Average service time', placeholder: '30', getDefaultValue: () => '30' },
          ],
        },
      },
      override: {
        functions: (originalImplementation) => withZeroQwaitAuth(originalImplementation),
      },
    }),
    Session.init({ tokenTransferMethod: 'header' }),
  ],
  getRedirectionURL: async (context) => {
    if (context.action === 'TO_AUTH') {
      return context.showSignIn === false ? '/signup' : '/login';
    }
    if (context.action === 'SUCCESS') {
      return context.redirectToPath || '/dashboard';
    }
    return undefined;
  },
});