import { useLocation } from "react-router-dom";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import Layout from "@/components/Layout";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error(
      "404 Error: User attempted to access non-existent route:",
      location.pathname,
    );
  }, [location.pathname]);

  return (
    <Layout>
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="text-center flex flex-col items-center gap-4">
          <span className="font-bebas text-8xl text-brand-primary opacity-30">404</span>
          <h1 className="font-bebas text-3xl text-black dark:text-white tracking-wide">
            Page not found
          </h1>
          <p className="font-dm-sans text-sm text-gray-500 dark:text-white/60">
            The page you're looking for doesn't exist.
          </p>
          <Link
            to="/"
            className="mt-2 px-6 py-2.5 rounded-full bg-brand-primary text-white font-dm-sans text-sm hover:opacity-90 transition-opacity"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    </Layout>
  );
};

export default NotFound;
