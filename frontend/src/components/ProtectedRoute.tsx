import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({
  children,
  requireSuperAdmin = false,
}: {
  children: React.ReactNode;
  requireSuperAdmin?: boolean;
}) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-500 text-sm animate-pulse">Verifying access...</div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (requireSuperAdmin && user.role !== "SUPER_ADMIN") {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-red-400 text-sm">Access denied — SUPER_ADMIN role required.</div>
      </div>
    );
  }

  return <>{children}</>;
}
