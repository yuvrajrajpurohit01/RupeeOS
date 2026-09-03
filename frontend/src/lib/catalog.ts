export interface Product {
  id: string;
  name: string;
  price: number;
  blurb: string;
  addon?: { name: string; price: number };
}

export const PRODUCTS: Product[] = [
  {
    id: "pro-headphones",
    name: "RupeePods Pro",
    price: 4999,
    blurb: "Wireless headphones for the end-to-end money journey demo.",
    addon: { name: "2-year protection", price: 499 },
  },
  {
    id: "smart-watch",
    name: "RupeeWatch S",
    price: 7999,
    blurb: "A higher-value checkout that is still inside autonomous bounds.",
    addon: { name: "Sport band", price: 799 },
  },
  {
    id: "high-value-kit",
    name: "Merchant Creator Kit",
    price: 12999,
    blurb: "Crosses the ₹10,000 verification threshold to demonstrate human approval.",
    addon: { name: "Priority setup", price: 1499 },
  },
];
