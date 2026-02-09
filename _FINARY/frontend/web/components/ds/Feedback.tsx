"use client";

export function Loading() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="spinner" />
    </div>
  );
}

export function ErrorState({ message = "Erreur de connexion API" }: { message?: string }) {
  return (
    <div className="flex items-center justify-center h-64">
      <p className="text-body text-loss">{message}</p>
    </div>
  );
}
