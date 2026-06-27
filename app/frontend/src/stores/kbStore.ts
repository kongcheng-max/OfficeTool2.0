import { create } from 'zustand';
import type { KnowledgeBaseItem } from '../api/kb';
import { getKBList } from '../api/kb';

interface KBState {
  list: KnowledgeBaseItem[];
  currentKBId: string | null;
  loading: boolean;
  fetchList: () => Promise<void>;
  setCurrentKB: (id: string | null) => void;
}

export const useKBStore = create<KBState>((set) => ({
  list: [],
  currentKBId: null,
  loading: false,

  fetchList: async () => {
    set({ loading: true });
    try {
      const list = await getKBList();
      set({ list, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  setCurrentKB: (id) => set({ currentKBId: id }),
}));
