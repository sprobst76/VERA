"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { DemoBar } from "@/components/shared/DemoBar";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { useAuthStore } from "@/store/auth";

const loginSchema = z.object({
  email: z.string().email("Ungültige E-Mail-Adresse"),
  password: z.string().min(6, "Mindestens 6 Zeichen"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { login, isLoading } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data: LoginForm) => {
    try {
      await login(data.email, data.password);
      router.push("/");
    } catch {
      toast.error("Ungültige Anmeldedaten");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      {/* Theme toggle top-right */}
      <div
        className="fixed top-4 right-4 rounded-lg overflow-hidden"
        style={{ backgroundColor: "rgb(var(--card))", border: "1px solid rgb(var(--border))" }}
      >
        <ThemeToggle />
      </div>

      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-ctp-blue">VERA</h1>
          <p className="mt-2 text-muted-foreground">
            Verwaltung, Einsatz, Reporting &amp; Assistenz
          </p>
        </div>

        <div className="bg-card rounded-xl shadow-md border border-border p-8">
          <h2 className="text-xl font-semibold mb-6 text-foreground">Anmelden</h2>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1 text-foreground">E-Mail</label>
              <input
                type="email"
                {...register("email")}
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
                placeholder="admin@example.de"
              />
              {errors.email && (
                <p className="text-ctp-red text-sm mt-1">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1 text-foreground">Passwort</label>
              <input
                type="password"
                {...register("password")}
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
                placeholder="••••••••"
              />
              {errors.password && (
                <p className="text-ctp-red text-sm mt-1">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-primary text-primary-foreground rounded-lg py-2.5 font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {isLoading ? "Anmelden..." : "Anmelden"}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-muted-foreground">
            Kein Zugang? Wende dich an deinen Administrator.
          </p>
        </div>
      </div>
      <DemoBar />
    </div>
  );
}
