import { create } from "zustand";
import type { FeeType, SearchItem } from "../api/types";

/** 화면 안의 임시 상태(서버에는 "견적 확인" 시점에 저장). */
export interface DraftLine {
  itemId: number;
  category: string;
  name: string;
  spec: string;
  unitFeeWon: number;
  feeType: FeeType;
  quantity: number;
  operatorFeeWon: number;
}

interface DraftState {
  municipalityCode: string | null;
  lines: DraftLine[];
  setMunicipality: (code: string | null) => void;
  addItem: (item: SearchItem, quantity?: number) => void;
  setQuantity: (itemId: number, quantity: number) => void;
  setOperatorFee: (itemId: number, won: number) => void;
  removeLine: (itemId: number) => void;
  reset: () => void;
}

export const MAX_LINES = 30;

export const useDraftStore = create<DraftState>((set) => ({
  municipalityCode: null,
  lines: [],
  setMunicipality: (code) =>
    set((s) => (s.municipalityCode === code ? s : { municipalityCode: code, lines: [] })),
  addItem: (item, quantity = 1) =>
    set((s) => {
      const found = s.lines.find((l) => l.itemId === item.item_id);
      if (found)
        return { lines: s.lines.map((l) => (l.itemId === item.item_id ? { ...l, quantity: Math.min(99, l.quantity + quantity) } : l)) };
      if (s.lines.length >= MAX_LINES) return s;
      return {
        lines: [
          ...s.lines,
          {
            itemId: item.item_id,
            category: item.category,
            name: item.name,
            spec: item.spec,
            unitFeeWon: item.fee_won,
            feeType: item.fee_type,
            quantity: Math.max(1, Math.min(99, quantity)),
            operatorFeeWon: 0,
          },
        ],
      };
    }),
  setQuantity: (itemId, quantity) =>
    set((s) => ({
      lines: s.lines.map((l) => (l.itemId === itemId ? { ...l, quantity: Math.max(1, Math.min(99, Math.trunc(quantity) || 1)) } : l)),
    })),
  setOperatorFee: (itemId, won) =>
    set((s) => ({
      lines: s.lines.map((l) => (l.itemId === itemId ? { ...l, operatorFeeWon: Math.max(0, Math.min(100_000_000, Math.trunc(won) || 0)) } : l)),
    })),
  removeLine: (itemId) => set((s) => ({ lines: s.lines.filter((l) => l.itemId !== itemId) })),
  reset: () => set({ municipalityCode: null, lines: [] }),
}));
