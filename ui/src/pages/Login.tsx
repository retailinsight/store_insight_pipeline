import { useEffect } from "react";
import { initiateLogin } from "@/utils/auth/oauthFlow";

/**
 * The login form lives in the external Authentication app.
 * This page just kicks off the OAuth2 redirect.
 */
export default function Login() {
  useEffect(() => {
    initiateLogin("/");
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-primary-100 to-brand-primary-50 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin w-10 h-10 border-4 border-brand-primary border-t-transparent rounded-full mx-auto mb-4"></div>
        <p className="font-dm-sans text-gray-600">
          Redirecting to sign-in&hellip;
        </p>
      </div>
    </div>
  );
}
