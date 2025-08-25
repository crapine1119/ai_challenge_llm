// (기존 내용은 유지하고, 아래만 추가)
export interface JDTemplate {
  id: string;                 // 템플릿 식별자(백엔드 id 또는 합성 id)
  name: string;               // 카드 타이틀
  summary: string;            // 카드에 보일 요약/첫 단락
  sections: string[];         // 섹션 아웃라인
  source: 'db' | 'generated' | 'preset';
  style_label?: string;       // (선택) 스타일 라벨
}
