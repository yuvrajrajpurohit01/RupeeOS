import { CheckoutOrder } from "./types";

interface RazorpaySuccess {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => {
      open: () => void;
      on: (event: string, callback: (response: unknown) => void) => void;
    };
  }
}

let scriptPromise: Promise<void> | null = null;

function loadRazorpay(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("Checkout is browser-only"));
  if (window.Razorpay) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Could not load Razorpay Checkout"));
    document.body.appendChild(script);
  });
  return scriptPromise;
}

export async function openRazorpayCheckout(
  order: CheckoutOrder,
  customerName: string,
  onSuccess: (response: RazorpaySuccess) => Promise<void>
): Promise<"success" | "failed" | "dismissed"> {
  await loadRazorpay();
  if (!window.Razorpay) throw new Error("Razorpay Checkout did not initialize");

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (value: "success" | "failed" | "dismissed") => {
      if (!settled) {
        settled = true;
        resolve(value);
      }
    };
    const checkout = new window.Razorpay!({
      key: order.key,
      amount: order.amount_subunits,
      currency: order.currency,
      name: order.name,
      description: order.description,
      order_id: order.razorpay_order_id,
      prefill: { name: customerName },
      notes: { money_id: order.money_id },
      theme: { color: "#2b5cff" },
      handler: async (response: RazorpaySuccess) => {
        try {
          await onSuccess(response);
          finish("success");
        } catch (error) {
          reject(error);
        }
      },
      modal: { ondismiss: () => finish("dismissed") },
    });
    checkout.on("payment.failed", () => finish("failed"));
    checkout.open();
  });
}
