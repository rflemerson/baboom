import { Routes } from '@angular/router';
import { ProteinListComponent } from './features/proteins/pages/protein-list/protein-list.component';

export const routes: Routes = [
    {
        path: 'proteins',
        component: ProteinListComponent,
        title: 'Protein Comparison'
    },
    {
        path: '',
        redirectTo: 'proteins',
        pathMatch: 'full'
    }
];
