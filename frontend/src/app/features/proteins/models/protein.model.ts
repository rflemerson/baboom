export interface Protein {
  id: number;
  brand: string;
  name: string;
  types: string[];             // Alterado para array de strings
  processingType?: 'Isolado' | 'Concentrado' | 'Hidrolisado'; // Opcional, apenas para whey
  weight: number;               // Total weight in grams
  price: number;                // Price (in your preferred currency)
  proteinConcentration: number; // Protein percentage (e.g., 70 represents 70%)
  totalProtein: number;         // Total protein in grams (can be calculated as: weight * proteinConcentration / 100)
  origin: 'Animal' | 'Vegetal' | 'Misto';  // Adicionado "Misto" para blends
  packaging: 'refil' | 'pote';  // Packaging type (refill or pot)
}
