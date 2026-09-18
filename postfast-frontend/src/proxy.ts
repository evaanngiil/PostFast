import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function proxy(request: NextRequest) {
  const token = request.cookies.get('aipost_session_id')?.value;
  const path = request.nextUrl.pathname;

  // Rutas públicas
  const isPublicRoute = path === '/login' || path.startsWith('/_next') || path.startsWith('/api') || path.startsWith('/assets') || path === '/email-confirmed' || path === '/verify-email';

  if (!token && !isPublicRoute) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};
