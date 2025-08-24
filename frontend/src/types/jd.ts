export type JDStatus = 'draft' | 'refining' | 'done' | 'error'
export interface JDItem {
  id: string
  title: string
  role: string
  companyStyle?: string
  createdAt: string
  status: JDStatus
}
