import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DataViewModule } from 'primeng/dataview';
import { ProteinItemComponent } from '../protein-item/protein-item.component';
import { ProteinService } from '../../services/protein.service';
import { Protein } from '../../models/protein.model';
import { Observable } from 'rxjs';

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
export class ProteinListComponent implements OnInit {
  proteins$: Observable<Protein[]> | undefined;

  constructor(private proteinService: ProteinService) { }

  ngOnInit() {
    this.proteins$ = this.proteinService.getProteins();
  }
}
