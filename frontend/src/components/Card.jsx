import React from 'react';

export const Card = ({ title, children, className = '', right }) => (
  <div className={`bg-white border border-slate-200 rounded-2xl p-5 shadow-sm ${className}`}>
    {title && (
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-slate-600">{title}</h3>
        {right}
      </div>
    )}
    {children}
  </div>
);