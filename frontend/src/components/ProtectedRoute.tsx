import React from "react";
import { SessionAuth } from "supertokens-auth-react/recipe/session";
import { useAuth } from "../contexts/AuthContext";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { loading } = useAuth();

  return (
    <SessionAuth>
      {loading ? (
        <div className="flex h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
        </div>
      ) : (
        <>{children}</>
      )}
    </SessionAuth>
  );
};

export default ProtectedRoute;
