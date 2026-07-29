import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAppDispatch } from "@/store/hooks";
import { authorize } from "@/store/slices/authSlice";
import { consumeReturnTo, initiateLogin } from "@/utils/auth/oauthFlow";

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const errorParam = searchParams.get("error");
    const errorDescription = searchParams.get("error_description");

    if (errorParam) {
      setError(errorDescription ?? errorParam);
      return;
    }

    if (!code || !state) {
      setError("Invalid callback \u2014 missing authorization code or state.");
      return;
    }

    dispatch(authorize({ code, state }))
      .unwrap()
      .then((result) => {
        const returnTo = consumeReturnTo();
        const permissions = result.permissions;

        if (permissions.length > 0) {
          navigate(returnTo, { replace: true });
        } else {
          navigate(returnTo, { replace: true });
        }
      })
      .catch((err: string) => {
        setError(err || "Authentication failed.");
      });
  }, [dispatch, navigate, searchParams]);

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-brand-primary-100 to-brand-primary-50 flex items-center justify-center px-4">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8 text-center">
          <h2 className="font-bebas text-2xl text-red-600 mb-4 tracking-wide">
            Login Failed
          </h2>
          <p className="font-dm-sans text-gray-700 mb-6">{error}</p>
          <button
            onClick={() => initiateLogin("/")}
            className="w-full bg-brand-primary text-white font-dm-sans font-medium py-2 px-4 rounded-lg hover:opacity-90 transition-opacity"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-primary-100 to-brand-primary-50 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin w-10 h-10 border-4 border-brand-primary border-t-transparent rounded-full mx-auto mb-4" />
        <p className="font-dm-sans text-gray-600">Completing sign-in</p>
      </div>
    </div>
  );
}
