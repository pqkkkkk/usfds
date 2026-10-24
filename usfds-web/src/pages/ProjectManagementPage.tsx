import { ProjectManagementView } from '../components/modules/project_management/ProjectManagementView';

export function ProjectManagementPage() {
	return (
		<div className="flex-1 flex flex-col h-full overflow-hidden">
			<ProjectManagementView />
		</div>
	);
}

export default ProjectManagementPage;
