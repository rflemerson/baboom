import { Protein } from '../models/protein.model';

export const PROTEINS: Protein[] = [
  {
    id: 1,
    name: '100% Pure',
    brand: 'IntegralMédica',
    types: ['Whey'],
    processingType: 'Concentrado',
    weight: 907,
    price: 102.35,
    proteinConcentration: 70,
    totalProtein: 907 * 0.70,
    origin: 'Animal',
    packaging: 'pote'
  },
  {
    id: 2,
    name: 'Whey Protein Concentrado',
    brand: 'Dux Nutrition',
    types: ['Whey'],
    processingType: 'Concentrado',
    weight: 900,
    price: 142.38,
    proteinConcentration: 66.67,
    totalProtein: 900 * 0.6667,
    origin: 'Animal',
    packaging: 'pote'
  },
  {
    id: 3,
    name: 'Proteína de Ervilha 80%',
    brand: 'Relva Verde',
    types: ['Ervilha'],
    weight: 200,
    price: 15.90,
    proteinConcentration: 80,
    totalProtein: 200 * 0.80,
    origin: 'Vegetal',
    packaging: 'refil'
  },
  {
    id: 4,
    name: 'Proteína Isolada de Soja 90%',
    brand: 'Empório Quatro Estrelas',
    types: ['Soja'],
    weight: 100,
    price: 21.90,
    proteinConcentration: 90,
    totalProtein: 100 * 0.90,
    origin: 'Vegetal',
    packaging: 'pote'
  },
  {
    id: 5,
    name: 'Proteína Texturizada de Soja (PTS)',
    brand: 'Quintal Mercado Saudável',
    types: ['Soja'],
    weight: 100,
    price: 2.00,
    proteinConcentration: 46,
    totalProtein: 100 * 0.46,
    origin: 'Vegetal',
    packaging: 'refil'
  },
  // Exemplo de um blend
  {
    id: 6,
    name: 'Blend Vegetal Premium',
    brand: 'Veggie Power',
    types: ['Ervilha', 'Arroz'],
    weight: 500,
    price: 59.90,
    proteinConcentration: 75,
    totalProtein: 500 * 0.75,
    origin: 'Vegetal',
    packaging: 'pote'
  }
];
