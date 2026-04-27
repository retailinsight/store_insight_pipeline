import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!email || !password) {
      const errorMsg = "Please enter both email and password";
      setError(errorMsg);
      toast({
        title: "Missing fields",
        description: errorMsg,
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "Login failed. Please try again.";
      setError(errorMsg);
      // Error is already handled by useAuth hook
      console.error("Login error:", error);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-primary-100 to-brand-primary-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo/Header */}
        <div className="text-center mb-8">
          <h1 className="font-bebas text-4xl text-brand-primary tracking-wide mb-2">
            Store Insight
          </h1>
          <p className="font-dm-sans text-gray-600">
            Retail Performance Dashboard
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h2 className="font-bebas text-2xl text-black mb-6 tracking-wide">
            Sign In
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Error Message */}
            {error && (
              <div
                data-testid="login-error-message"
                className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded font-dm-sans text-sm"
              >
                {error}
              </div>
            )}

            {/* Email Input */}
            <div className="space-y-2">
              <Label htmlFor="email" className="font-dm-sans font-medium">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="manager@storeinsight.io"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
                className="font-dm-sans"
                data-testid="login-email-input"
              />
            </div>

            {/* Password Input */}
            <div className="space-y-2">
              <Label htmlFor="password" className="font-dm-sans font-medium">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                className="font-dm-sans"
                data-testid="login-password-input"
              />
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={isLoading}
              className="w-full mt-6 bg-brand-primary hover:opacity-90 text-white font-dm-sans font-medium py-2 h-10"
              data-testid="login-submit-button"
            >
              {isLoading ? "Signing in..." : "Sign In"}
            </Button>
          </form>

          {/* Demo Credentials */}
          <div className="hidden mt-6 pt-6 border-t border-gray-200">
            <p className="font-dm-sans text-xs text-gray-600 mb-3">
              Demo credentials:
            </p>

            {/* Store Manager */}
            <div className="mb-3">
              <p className="font-dm-sans text-xs font-medium text-gray-700 mb-1">
                Store Manager (roleId: 1)
              </p>
              <div className="space-y-1 font-dm-sans text-xs text-gray-700 bg-gray-50 p-3 rounded">
                <p>Email: <code className="bg-white px-1">manager@storeinsight.io</code></p>
                <p>Password: <code className="bg-white px-1">manager123</code></p>
              </div>
            </div>

            {/* Cluster Lead */}
            <div>
              <p className="font-dm-sans text-xs font-medium text-gray-700 mb-1">
                Cluster Lead (roleId: 2 - Can switch stores)
              </p>
              <div className="space-y-1 font-dm-sans text-xs text-gray-700 bg-gray-50 p-3 rounded">
                <p>Email: <code className="bg-white px-1">clusterlead@storeinsight.io</code></p>
                <p>Password: <code className="bg-white px-1">clusterlead123</code></p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
