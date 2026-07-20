export type BestsellerBook = {
  id: string;
  rank: number;
  title: string;
  author: string | null;
  publisher: string | null;
  category: string | null;
  sales_volume: number | null;
};

export type BestsellerTheme = {
  category: string;
  total_volume: number;
  book_count: number;
};

export type MarketInsights = {
  source: string;
  period_label: string | null;
  last_updated: string | null;
  books: BestsellerBook[];
  themes: BestsellerTheme[];
};
