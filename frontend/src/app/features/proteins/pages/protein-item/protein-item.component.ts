import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { TagModule } from 'primeng/tag';
import { ChipModule } from 'primeng/chip'; // Adicionado módulo Chip
import { Protein } from '../../models/protein.model';

@Component({
  selector: 'app-protein-item',
  standalone: true,
  imports: [
    CommonModule,
    ButtonModule,
    TagModule,
    ChipModule // Importando ChipModule
  ],
  templateUrl: './protein-item.component.html',
  styleUrls: ['./protein-item.component.css']
})
export class ProteinItemComponent {
  @Input() protein!: Protein;

  getTypeClasses(type: string): string {
    const typeClasses: { [key: string]: string } = {
      'Whey': 'bg-blue-600 text-white',          // Azul intenso
      'Ervilha': 'bg-emerald-600 text-white',     // Verde esmeralda
      'Soja': 'bg-amber-600 text-black',          // Âmbar
      'Arroz': 'bg-orange-500 text-white',        // Laranja
      'Cânhamo': 'bg-violet-600 text-white',      // Violeta
      'Vegetal': 'bg-lime-500 text-black'         // Verde limão
    };
    return typeClasses[type] || 'bg-gray-500 text-white'; // Fallback
  }

  // Classes para origem
  getOriginClasses(origin: string): string {
    return {
      'Animal': 'bg-red-500 text-white',
      'Vegetal': 'bg-green-400 text-black',
      'Misto': 'bg-pink-500 text-white'
    }[origin] || 'bg-gray-400 text-white';
  }
}
