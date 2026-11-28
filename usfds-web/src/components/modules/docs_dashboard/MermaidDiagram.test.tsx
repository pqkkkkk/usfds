import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { MermaidDiagram } from './MermaidDiagram';

vi.mock('mermaid', () => ({
	default: {
		initialize: vi.fn(),
		render: vi.fn(async () => ({ svg: '<svg><text>Sơ đồ</text></svg>' })),
	},
}));

it('zooms_and_resets_large_diagram', async () => {
	render(<MermaidDiagram code="flowchart LR\nA --> B" />);
	fireEvent.click(await screen.findByRole('button', { name: 'Phóng to' }));
	const dialog = screen.getByRole('dialog');
	const diagram = within(dialog).getByLabelText('Vùng sơ đồ');
	expect(diagram).toHaveStyle({ width: '100%' });
	fireEvent.click(within(dialog).getByRole('button', { name: 'Tăng mức thu phóng' }));
	expect(diagram).toHaveStyle({ width: '125%' });
	fireEvent.click(within(dialog).getByRole('button', { name: 'Giảm mức thu phóng' }));
	expect(diagram).toHaveStyle({ width: '100%' });
	fireEvent.click(within(dialog).getByRole('button', { name: 'Tăng mức thu phóng' }));
	fireEvent.click(within(dialog).getByRole('button', { name: 'Đặt lại mức thu phóng' }));
	expect(diagram).toHaveStyle({ width: '100%' });
});

it('closes_viewer_and_restores_focus', async () => {
	render(<MermaidDiagram code="flowchart LR\nA --> B" />);
	const open = await screen.findByRole('button', { name: 'Phóng to' });
	open.focus();
	fireEvent.click(open);
	expect(within(screen.getByRole('dialog')).getByRole('button', { name: 'Đóng' })).toHaveFocus();
	fireEvent.keyDown(window, { key: 'Escape' });
	expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
	expect(open).toHaveFocus();
});

it('keeps_keyboard_focus_in_the_viewer_and_reaches_the_scroll_region', async () => {
	render(<MermaidDiagram code="flowchart LR\nA --> B" />);
	fireEvent.click(await screen.findByRole('button', { name: 'Phóng to' }));
	const dialog = screen.getByRole('dialog');
	const scroll = within(dialog).getByLabelText('Cuộn sơ đồ');
	expect(scroll).toHaveAttribute('tabindex', '0');
	scroll.focus();
	fireEvent.keyDown(window, { key: 'Tab' });
	expect(within(dialog).getByRole('button', { name: 'Giảm mức thu phóng' })).toHaveFocus();
});
