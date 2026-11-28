import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { RichDocRenderer } from './RichDocRenderer';

it('opens_architecture_source_and_relative_links', () => {
	const onSelectFileRef = vi.fn();
	const onSelectPlan = vi.fn();
	render(
		<RichDocRenderer
			markdown="[Runtime](01-context-and-runtime.md#4-clientserverworker-runtime--remote-compute)"
			sourcePath="docs/arch/README.md"
			onSelectFileRef={onSelectFileRef}
			onSelectIssue={vi.fn()}
			onSelectPlan={onSelectPlan}
		/>
	);
	fireEvent.click(screen.getByRole('button', { name: /Runtime/ }));
	expect(onSelectPlan).not.toHaveBeenCalled();
	expect(onSelectFileRef).toHaveBeenCalledWith(
		'docs/arch/01-context-and-runtime.md#4-clientserverworker-runtime--remote-compute'
	);
});

it('reports_links_outside_the_repository', () => {
	const onSelectFileRef = vi.fn();
	render(
		<RichDocRenderer
			markdown="[Ngoài repo](../../../outside.md)"
			sourcePath="docs/arch/README.md"
			onSelectFileRef={onSelectFileRef}
			onSelectIssue={vi.fn()}
		/>
	);
	fireEvent.click(screen.getByRole('button', { name: /Ngoài repo/ }));
	expect(screen.getByRole('alert')).toHaveTextContent(/ngoài repository/);
	expect(onSelectFileRef).not.toHaveBeenCalled();
});
