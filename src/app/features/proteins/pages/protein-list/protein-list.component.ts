import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DataViewModule } from 'primeng/dataview';
import { PROTEINS } from '../../constants/proteins.data';
import { ProteinItemComponent } from '../protein-item/protein-item.component';

@Component({
  selector: 'app-protein-list',
  standalone: true,
  imports: [
    CommonModule,
    DataViewModule,
    ProteinItemComponent
  ],
  templateUrl: './protein-list.component.html',
  styleUrls: ['./protein-list.component.css']
})
export class ProteinListComponent {
  proteins = PROTEINS;
}
