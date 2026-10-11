import { DataManagementModule } from '../components/modules/DataManagementModule';

interface DataManagementPageProps {
  onOpenInspector?: (item: any) => void;
}

export function DataManagementPage({ onOpenInspector = () => {} }: DataManagementPageProps) {
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <DataManagementModule onOpenInspector={onOpenInspector} />
    </div>
  );
}
