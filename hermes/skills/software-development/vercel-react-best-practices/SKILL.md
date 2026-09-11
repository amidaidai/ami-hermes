---
name: vercel-react-best-practices
description: "Vercel React/Next.js Best Practices — performance optimization, web design guidelines, and frontend architecture patterns from Vercel Engineering"
version: 1.0.0
author: Hermes Agent (adapted from vercel-labs/agent-skills)
tags: [frontend, react, nextjs, vercel, performance, web-design]
---

# Vercel React/Next.js Best Practices

Official best-practice skills from Vercel Labs for building production-quality React and Next.js applications.

## Skills Included

### Vercel React Best Practices
- React Server Components (RSC) usage patterns
- Server Actions vs API routes
- Streaming and Suspense boundaries
- Image optimization with `next/image`
- Route handlers and middleware
- Caching strategies (full route, data, ISR)
- Edge runtime considerations

### Web Design Guidelines
- Typography and spacing systems
- Color theory and accessibility (WCAG)
- Responsive design patterns
- Layout and grid systems
- Component composition
- Loading states and error boundaries
- Animation performance
- Form design and validation UX

## Installation
```bash
npx skills add vercel-labs/agent-skills
```

## Usage Patterns

For React/Next.js performance:
```bash
npx skills add vercel-react-best-practices
```

For web design:
```bash
npx skills add web-design-guidelines
```

## Key Principles
- Prefer React Server Components by default
- Move client logic to Server Actions when possible
- Use streaming for data-dependent UI
- Optimize images, fonts, and third-party scripts
- Measure Core Web Vitals in CI
- Design for accessibility first, then enhance
