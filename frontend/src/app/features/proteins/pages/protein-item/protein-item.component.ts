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
      'Whey': 'bg-blue-600 text-white',
      'Pea': 'bg-emerald-600 text-white',
      'Soy': 'bg-amber-600 text-black',
      'Rice': 'bg-orange-500 text-white',
      'Hemp': 'bg-violet-600 text-white',
      'Plant': 'bg-lime-500 text-black'
    };
    return typeClasses[type] || 'bg-gray-500 text-white'; // Fallback
  }

  // Classes for origin
  getOriginClasses(origin: string): string {
    return {
      'Animal': 'bg-red-500 text-white',
      'Plant': 'bg-green-400 text-black',
      'Blend': 'bg-pink-500 text-white'
    }[origin] || 'bg-gray-400 text-white';
  }
}
