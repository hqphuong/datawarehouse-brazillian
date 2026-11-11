export const BLUE = '#7aa7e0';
export const RED = '#e59a9a';
export const AMBER = '#e8c27a';
export const GRID = '#eef2f6';
export const MUTED = '#94a3b8';

export const TABS = [
  { id: 'dashboard', label: 'BI Dashboard', icon: 'dashboard' },
  { id: 'dss', label: 'DSS Action Center', icon: 'dss' },
  { id: 'olap', label: 'OLAP Query', icon: 'olap' },
  { id: 'etl', label: 'ETL Monitor', icon: 'etl' },
];

export const STATES = ['SP', 'RJ', 'MG', 'RS', 'PR'];
export const CATS = ['Electronics', 'Furniture', 'Toys', 'Health & Beauty'];
export const QTRS = ['Q1', 'Q2', 'Q3', 'Q4'];
export const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export const DIMS = { loc: 'Location', cat: 'Product Category', qtr: 'Quarter' };
export const MEAS = { orders: 'Order Count', freight: 'Total Freight', delay: 'Avg Delay (days)', rev: 'Revenue' };

// Sinh dữ liệu thô cho màn OLAP Query
export const RAW_OLAP = [];
STATES.forEach((s, i) => CATS.forEach((c, j) => QTRS.forEach((q, k) => {
  const n = 120 + ((i * 37 + j * 53 + k * 29) % 220) + (s === 'SP' ? 400 : 0);
  RAW_OLAP.push({ 
    loc: s, 
    cat: c, 
    qtr: q, 
    orders: n, 
    freight: Math.round(n * (17 + j * 2.5 + (i % 3))), 
    delay: +(1.5 + ((i * 7 + j * 3 + k) % 9) * 0.45).toFixed(1), 
    rev: Math.round(n * (95 + j * 40)) 
  });
})));