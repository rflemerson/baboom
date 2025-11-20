export interface Protein {
  id: number;
  brand: string;
  name: string;
  types: string[];
  processingType?: 'Isolate' | 'Concentrate' | 'Hydrolyzed';
  weight: number;               // Total weight in grams
  price: number;                // Price (in your preferred currency)
  proteinConcentration: number; // Protein percentage (e.g., 70 represents 70%)
  totalProtein: number;         // Total protein in grams
  origin: 'Animal' | 'Plant' | 'Blend';
  packaging: 'Refill' | 'Container';
}
