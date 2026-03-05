import { create } from 'zustand';

const useProjectStore = create((set) => ({
  projectId: null,
  status: null,
  dataProfile: null,
  columnMap: null,
  objectives: null,
  slides: [],
  chatHistory: [],
  pptxUrl: null,
  error: null,

  setProject: (id, status) => set({ projectId: id, status }),
  setProfile: (profile, columnMap) => set({ dataProfile: profile, columnMap }),
  setObjectives: (objectives) => set({ objectives }),
  setSlides: (slides) => set({ slides }),
  setPptxUrl: (url) => set({ pptxUrl: url }),
  setStatus: (status) => set({ status }),
  setError: (error) => set({ error }),
  addChatMessage: (msg) => set((state) => ({ chatHistory: [...state.chatHistory, msg] })),
  setChatHistory: (history) => set({ chatHistory: history }),
  updateSlide: (slideIndex, updates) =>
    set((state) => ({
      slides: state.slides.map((s) =>
        s.slide_index === slideIndex ? { ...s, ...updates } : s
      ),
    })),
  reset: () =>
    set({
      projectId: null, status: null, dataProfile: null, columnMap: null,
      objectives: null, slides: [], chatHistory: [], pptxUrl: null, error: null,
    }),
}));

export default useProjectStore;
