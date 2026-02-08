"use client";

import { usePortfolio } from "@/lib/hooks/useApi";
import { formatEUR, formatCurrency, formatPct, pnlColor } from "@/lib/utils";

export default function PortfolioPage() {
  const { data: positions, isLoading, error } = usePortfolio();

  if (isLoading) return <div className="text-gray-500">Chargement...</div>;
  if (error) return <div className="text-red-500">Erreur: {error.message}</div>;

  const totalValue = positions?.reduce((s, p) => s + p.value_eur, 0) ?? 0;
  const totalPnl = positions?.reduce((s, p) => s + p.pnl_eur, 0) ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Portfolio</h2>
        <div className="text-right">
          <p className="text-xl font-bold">{formatEUR(totalValue)}</p>
          <p className={`text-sm ${pnlColor(totalPnl)}`}>
            {formatEUR(totalPnl)} ({formatPct(totalValue > 0 ? (totalPnl / (totalValue - totalPnl)) * 100 : 0)})
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-500">Position</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500">Qté</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500">PRU</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500">Cours</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500">Valeur EUR</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500">P&amp;L</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500">Poids</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {positions?.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-900">{p.ticker}</div>
                  <div className="text-xs text-gray-500">{p.name}</div>
                </td>
                <td className="text-right px-4 py-3">{p.quantity}</td>
                <td className="text-right px-4 py-3">
                  {p.avg_cost ? formatCurrency(p.avg_cost, p.currency) : "—"}
                </td>
                <td className="text-right px-4 py-3">
                  {p.current_price ? formatCurrency(p.current_price, p.currency) : "—"}
                </td>
                <td className="text-right px-4 py-3 font-medium">
                  {formatEUR(p.value_eur)}
                </td>
                <td className={`text-right px-4 py-3 ${pnlColor(p.pnl_eur)}`}>
                  {formatEUR(p.pnl_eur)}
                  <div className="text-xs">{formatPct(p.pnl_pct)}</div>
                </td>
                <td className="text-right px-4 py-3 text-gray-500">
                  {p.weight_pct.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
