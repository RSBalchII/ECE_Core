import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from './Button';

describe('Button Component', () => {
  describe('Rendering', () => {
    it('renders button with children', () => {
      render(<Button>Click Me</Button>);
      
      expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
    });

    it('renders button with custom className', () => {
      render(<Button className="custom-class">Test</Button>);
      
      const button = screen.getByRole('button');
      expect(button).toHaveClass('custom-class');
    });

    it('applies variant classes correctly', () => {
      const { rerender } = render(<Button variant="primary">Primary</Button>);
      expect(screen.getByRole('button')).toHaveClass('btn-primary');

      rerender(<Button variant="ghost">Ghost</Button>);
      expect(screen.getByRole('button', { name: /ghost/i })).not.toHaveClass('btn-primary');

      rerender(<Button variant="icon">Icon</Button>);
      expect(screen.getByRole('button', { name: /icon/i })).not.toHaveClass('btn-primary');
    });
  });

  describe('Variants', () => {
    it('renders primary button with default styles', () => {
      render(<Button variant="primary">Primary</Button>);
      
      const button = screen.getByRole('button');
      expect(button).toHaveClass('btn-primary');
    });

    it('renders ghost button with transparent background', () => {
      render(<Button variant="ghost">Ghost</Button>);
      
      const button = screen.getByRole('button');
      expect(button.style.background).toBe('transparent');
    });

    it('renders icon button with no border', () => {
      render(<Button variant="icon">Icon</Button>);
      
      const button = screen.getByRole('button');
      expect(button.style.border).not.toBe('solid');
      expect(button.style.padding).toBe('0px');
    });
  });

  describe('Active State', () => {
    it('applies active styles to primary button', () => {
      render(<Button variant="primary" active>Active</Button>);
      
      const button = screen.getByRole('button');
      expect(button.style.filter).toBe('brightness(1.2)');
    });

    it('applies active styles to ghost button', () => {
      render(<Button variant="ghost" active>Active Ghost</Button>);
      
      const button = screen.getByRole('button');
      expect(button.style.background.replace(/ /g, '')).toBe('rgba(255,255,255,0.1)');
      expect(button.style.border).toBe('1px solid var(--border-subtle)');
    });

    it('does not apply active styles when inactive', () => {
      render(<Button variant="ghost" active={false}>Inactive</Button>);
      
      const button = screen.getByRole('button');
      expect(button.style.background).toBe('transparent');
      expect(button.style.border).not.toBe('solid');
    });
  });

  describe('Click Handling', () => {
    it('calls onClick handler when clicked', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();
      
      render(<Button onClick={handleClick}>Click Me</Button>);
      
      await user.click(screen.getByRole('button'));
      
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('passes event to onClick handler', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();
      
      render(<Button onClick={handleClick}>Click</Button>);
      
      await user.click(screen.getByRole('button'));
      
      expect(handleClick).toHaveBeenCalledWith(expect.objectContaining({
        type: 'click',
      }));
    });
  });

  describe('Disabled State', () => {
    it('renders disabled button', () => {
      render(<Button disabled>Disabled</Button>);
      
      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('does not call onClick when disabled', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();
      
      render(<Button disabled onClick={handleClick}>Disabled</Button>);
      
      await user.click(screen.getByRole('button'));
      
      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('HTML Attributes', () => {
    it('passes through HTML attributes', () => {
      render(
        <Button 
          id="test-button"
          aria-label="Test Button"
          data-testid="test"
          type="submit"
        >
          Test
        </Button>
      );
      
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('id', 'test-button');
      expect(button).toHaveAttribute('aria-label', 'Test Button');
      expect(button).toHaveAttribute('data-testid', 'test');
      expect(button).toHaveAttribute('type', 'submit');
    });
  });

  describe('Accessibility', () => {
    it('has proper button role', () => {
      render(<Button>Accessible</Button>);
      
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('can be focused', () => {
      render(<Button>Focusable</Button>);
      
      const button = screen.getByRole('button');
      button.focus();
      
      expect(document.activeElement).toBe(button);
    });
  });
});
