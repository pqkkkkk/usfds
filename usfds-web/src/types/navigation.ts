export type AppModule = 
  | 'data-management'
  | 'model-management'
  | 'rule-management'
  | 'detection'
  | 'investigation'
  | 'insight-report';

export interface Project {
  id: string;
  name: string;
  description?: string;
  activeDatasetId?: string;
  activeModelId?: string;
}

export interface PipelineStep {
  id: string;
  stepNumber: number;
  label: string;
  description?: string;
  state: 'completed' | 'active' | 'locked';
}

// Raw JSON lineage schema from back-end
export interface LineageRawNode {
  id: string;
  stage: 'RAW' | 'MAPPED' | 'PRE_PROCESSED' | string;
  created_at: string;
  parent_id: string | null;
  name?: string;
  rows?: number;
  checksum?: string;
}

export interface LineageRawEdge {
  source: string;
  target: string;
}

export interface LineageDataResponse {
  dataset_id: string;
  nodes: LineageRawNode[];
  edges: LineageRawEdge[];
}

// Node with hierarchical children for Tree View
export interface LineageTreeNode extends LineageRawNode {
  children: LineageTreeNode[];
}

// Node with computed coordinates for Canvas / DAG View
export interface LineageCanvasNode extends LineageRawNode {
  x: number;
  y: number;
  width: number;
  height: number;
  level: number;
}

export interface DatasetEntity {
  id: string;
  name: string;
  description: string;
  category: string;
  createdAt: string;
  updatedAt: string;
  totalArtifacts: number;
  artifacts?: any[];
}
