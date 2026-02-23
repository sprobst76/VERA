import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// NEXT_PUBLIC_DEMO_SLUG wird zur Build-Zeit eingebettet, z.B. "demo-a3f9b2c1"
const DEMO_SLUG = process.env.NEXT_PUBLIC_DEMO_SLUG;

export function middleware(request: NextRequest) {
  if (!DEMO_SLUG) return NextResponse.next();

  const { pathname } = request.nextUrl;

  // /demo-abc123 oder /demo-abc123/ → Cookie setzen + Redirect auf /
  if (pathname === `/${DEMO_SLUG}` || pathname.startsWith(`/${DEMO_SLUG}/`)) {
    const response = NextResponse.redirect(new URL("/", request.url));
    response.cookies.set("vera_demo", "1", {
      httpOnly: false,        // muss im Browser lesbar sein (DemoBar)
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 30,  // 30 Tage
      path: "/",
    });
    return response;
  }

  return NextResponse.next();
}

export const config = {
  // Statische Assets und _next-Intern-Routen ausschließen
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
