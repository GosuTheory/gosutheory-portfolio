# CLAUDE.md - AI Assistant Guide for GosuTheory Portfolio

> **Last Updated**: November 21, 2025
> **Project Status**: Initial Setup
> **Repository**: gosutheory-portfolio

## Overview

This is a personal portfolio website project for GosuTheory. This document provides AI assistants with comprehensive guidance on the codebase structure, development workflows, and conventions to follow when working on this project.

## Project Status

**Current State**: This is a new repository being set up. The project structure and technology stack will be established as development progresses.

## Intended Project Structure

As this portfolio develops, the typical structure should follow modern web development best practices:

```
gosutheory-portfolio/
├── src/                    # Source code
│   ├── components/         # Reusable UI components
│   ├── pages/              # Page components or routes
│   ├── assets/             # Images, fonts, static files
│   ├── styles/             # CSS/SCSS/styled-components
│   ├── utils/              # Utility functions
│   ├── hooks/              # Custom React hooks (if React)
│   ├── services/           # API services, data fetching
│   └── types/              # TypeScript type definitions
├── public/                 # Static assets served directly
├── tests/                  # Test files
├── docs/                   # Additional documentation
├── .github/                # GitHub Actions, workflows, issue templates
├── package.json            # Dependencies and scripts
├── tsconfig.json           # TypeScript configuration
├── README.md               # User-facing documentation
└── CLAUDE.md               # This file - AI assistant guide
```

## Technology Stack Recommendations

### Frontend Framework Options
- **React** (with Next.js or Vite)
- **Vue.js** (with Nuxt or Vite)
- **Svelte/SvelteKit**
- **Vanilla HTML/CSS/JS** (for simplicity)

### Styling Options
- **Tailwind CSS** - Utility-first CSS framework
- **Styled Components** - CSS-in-JS
- **SCSS/SASS** - Enhanced CSS
- **CSS Modules** - Scoped CSS

### Build Tools
- **Vite** - Fast modern build tool
- **Webpack** - Comprehensive bundler
- **Parcel** - Zero-config bundler

### Additional Tools
- **TypeScript** - Type safety
- **ESLint** - Code linting
- **Prettier** - Code formatting
- **Jest/Vitest** - Testing framework
- **Playwright/Cypress** - E2E testing

## Development Workflows

### Getting Started
1. **Install Dependencies**
   ```bash
   npm install
   # or
   yarn install
   # or
   pnpm install
   ```

2. **Start Development Server**
   ```bash
   npm run dev
   # or
   yarn dev
   ```

3. **Build for Production**
   ```bash
   npm run build
   ```

4. **Run Tests**
   ```bash
   npm test
   ```

### Git Workflow

#### Branch Naming Convention
- Feature branches: `feature/descriptive-name`
- Bug fixes: `fix/issue-description`
- Hotfixes: `hotfix/critical-issue`
- Claude AI branches: `claude/claude-md-*` (auto-generated)

#### Commit Message Convention
Follow Conventional Commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Example: `feat: add hero section to homepage`

### Code Review Process
1. Create a feature branch
2. Make changes with clear, atomic commits
3. Push to remote
4. Create a pull request with description
5. Address review feedback
6. Merge after approval

## AI Assistant Conventions

### Core Principles
1. **Understand Before Changing**: Always read existing code before making modifications
2. **Maintain Consistency**: Follow existing patterns and conventions in the codebase
3. **Test Your Changes**: Ensure code runs and tests pass before committing
4. **Document Your Work**: Add comments for complex logic, update docs as needed
5. **Ask When Uncertain**: Clarify requirements before making assumptions

### Code Quality Standards

#### TypeScript (when used)
- Use strict mode
- Define interfaces for props and data structures
- Avoid `any` type - use `unknown` or proper types
- Export types alongside components

#### React Components (if using React)
- Use functional components with hooks
- Keep components small and focused (single responsibility)
- Extract reusable logic into custom hooks
- Props should have TypeScript interfaces
- Use meaningful component and variable names

#### Styling
- Follow BEM naming convention for CSS classes (if not using CSS-in-JS)
- Keep styles modular and component-scoped
- Use CSS variables for theming
- Ensure responsive design (mobile-first approach)
- Test across different screen sizes

#### Performance
- Optimize images (use WebP, lazy loading)
- Code split large bundles
- Minimize re-renders in React
- Use production builds for deployment
- Implement proper caching strategies

#### Accessibility (a11y)
- Use semantic HTML elements
- Include ARIA labels where needed
- Ensure keyboard navigation works
- Maintain proper heading hierarchy
- Test with screen readers
- Ensure color contrast ratios meet WCAG standards

#### Security
- Sanitize user inputs
- Avoid XSS vulnerabilities
- Use HTTPS for all external resources
- Keep dependencies updated
- Don't commit secrets or API keys
- Use environment variables for sensitive data

### File Organization

#### Naming Conventions
- **Components**: PascalCase (e.g., `HeroSection.tsx`)
- **Utilities**: camelCase (e.g., `formatDate.ts`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `API_ENDPOINTS.ts`)
- **Styles**: kebab-case or match component name
- **Types**: PascalCase with descriptive names (e.g., `UserProfile.ts`)

#### Component Structure
```typescript
// ComponentName.tsx
import { FC } from 'react';
import styles from './ComponentName.module.css';
import { ComponentNameProps } from './types';

/**
 * Brief description of component purpose
 */
export const ComponentName: FC<ComponentNameProps> = ({ prop1, prop2 }) => {
  // Hooks
  // Event handlers
  // Render logic

  return (
    <div className={styles.container}>
      {/* JSX */}
    </div>
  );
};
```

### Testing Guidelines
- Write unit tests for utility functions
- Write integration tests for components
- Write E2E tests for critical user flows
- Aim for meaningful coverage (not just high %)
- Test edge cases and error states
- Mock external dependencies

### Common Tasks

#### Adding a New Page
1. Create page component in `src/pages/`
2. Add route configuration (if using routing)
3. Create associated components in `src/components/`
4. Add styles
5. Update navigation/links
6. Test responsive behavior

#### Adding a New Component
1. Create component file with proper naming
2. Define TypeScript interfaces for props
3. Implement component logic
4. Add styles (scoped to component)
5. Write tests
6. Export from index file if needed

#### Updating Dependencies
1. Check for breaking changes in changelog
2. Update one major dependency at a time
3. Run tests after updating
4. Update code for breaking changes
5. Test the application thoroughly

#### Optimizing Performance
1. Run Lighthouse audit
2. Identify bottlenecks
3. Optimize images and assets
4. Implement code splitting
5. Add lazy loading where appropriate
6. Verify improvements with metrics

## Portfolio-Specific Guidelines

### Content Sections (Typical Portfolio Structure)
1. **Hero/Landing** - Name, title, brief introduction
2. **About** - Background, skills, interests
3. **Projects** - Showcase of work with descriptions
4. **Experience/Resume** - Work history and education
5. **Skills** - Technical and soft skills
6. **Contact** - Contact form or information
7. **Blog** (optional) - Articles and writings

### Design Considerations
- **Personal Branding**: Maintain consistent colors, fonts, and style
- **Visual Hierarchy**: Guide users through the content
- **Whitespace**: Don't clutter; use space effectively
- **Typography**: Choose readable, professional fonts
- **Color Scheme**: 2-3 primary colors + neutrals
- **Animations**: Subtle, purposeful, not distracting
- **Loading States**: Provide feedback for async operations

### Content Guidelines
- **Clear Headlines**: Descriptive and engaging
- **Concise Copy**: Get to the point quickly
- **Action-Oriented**: Use strong verbs
- **Proofread**: No typos or grammatical errors
- **Showcase Results**: Quantify achievements when possible
- **Tell a Story**: Make it personal and authentic

## Deployment

### Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Build succeeds without errors
- [ ] No console errors or warnings
- [ ] Responsive design verified
- [ ] Accessibility tested
- [ ] Performance optimized (Lighthouse score)
- [ ] SEO meta tags configured
- [ ] Analytics integrated (if desired)
- [ ] Favicon and app icons added
- [ ] 404 page created

### Deployment Platforms
- **Vercel** - Excellent for Next.js
- **Netlify** - Great for static sites and frameworks
- **GitHub Pages** - Free hosting for static sites
- **AWS Amplify** - Full-featured with AWS integration
- **Railway/Render** - Good for full-stack apps

### Environment Variables
- Use `.env.local` for local development
- Never commit `.env` files
- Document required environment variables in README
- Use different values for development/production

## Troubleshooting

### Common Issues

#### Build Failures
- Check Node.js version compatibility
- Clear cache: `rm -rf node_modules package-lock.json && npm install`
- Verify all imports are correct
- Check for TypeScript errors

#### Styling Issues
- Check CSS specificity conflicts
- Verify CSS modules are imported correctly
- Check responsive breakpoints
- Inspect browser dev tools

#### Performance Issues
- Check bundle size with analyzer
- Identify unnecessary re-renders
- Optimize images
- Review third-party scripts

## Resources

### Documentation Links (to be added)
- Project README: `README.md`
- API Documentation: TBD
- Design System: TBD
- Deployment Guide: TBD

### Useful External Resources
- [Web.dev](https://web.dev/) - Web development best practices
- [MDN Web Docs](https://developer.mozilla.org/) - Web technology reference
- [React Docs](https://react.dev/) - React documentation (if using React)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/) - TypeScript guide
- [Accessibility Guidelines](https://www.w3.org/WAI/WCAG21/quickref/) - WCAG reference

## Notes for AI Assistants

### When Starting a Task
1. Read this CLAUDE.md file
2. Explore the codebase structure
3. Check package.json for scripts and dependencies
4. Review recent commits to understand context
5. Ask clarifying questions if requirements are unclear

### When Making Changes
1. Use the TodoWrite tool to track multi-step tasks
2. Read existing files before modifying them
3. Follow the established patterns and conventions
4. Test changes locally before committing
5. Write clear commit messages
6. Update documentation if needed

### When Completing a Task
1. Verify all tests pass
2. Check for console errors
3. Review changes for quality and consistency
4. Commit with descriptive message
5. Push to the designated branch
6. Provide summary of changes made

### What to Avoid
- Don't make assumptions about technology stack until it's established
- Don't add unnecessary dependencies
- Don't skip testing
- Don't commit broken code
- Don't modify code without understanding it
- Don't ignore accessibility
- Don't sacrifice security for convenience

## Maintenance

This CLAUDE.md file should be updated when:
- Technology stack is chosen or changed
- New conventions are established
- Project structure evolves
- New tools are integrated
- Common issues are discovered
- Deployment process changes

---

**Remember**: This is a living document. Keep it updated as the project evolves to ensure it remains a valuable resource for AI assistants and developers working on this portfolio.
