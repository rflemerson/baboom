import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map, tap } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { Protein } from '../models/protein.model';

@Injectable({
    providedIn: 'root'
})
export class ProteinService {
    private apiUrl = `${environment.apiUrl}/products/`;

    constructor(private http: HttpClient) { }

    getProteins(): Observable<Protein[]> {
        return this.http.get<any[]>(this.apiUrl).pipe(
            tap(products => console.log('API Response:', products)),
            map(products => products.map(product => this.mapProductToProtein(product)))
        );
    }

    private mapProductToProtein(product: any): Protein {
        // Find the lowest price among all stores
        let minPrice = 0;
        if (product.stores && product.stores.length > 0) {
            const prices = product.stores
                .map((store: any) => store.latest_price?.price)
                .filter((price: any) => price !== undefined && price !== null)
                .map((price: any) => parseFloat(price));

            if (prices.length > 0) {
                minPrice = Math.min(...prices);
            }
        }

        // Get protein concentration from the first nutrition profile if available
        let proteinConcentration = 0;
        let totalProtein = 0;

        if (product.nutrition_profiles && product.nutrition_profiles.length > 0) {
            const profile = product.nutrition_profiles[0];
            if (profile.nutritional_info && profile.nutritional_info.length > 0) {
                const info = profile.nutritional_info[0];
                const servingSize = info.serving_size_grams || 0;
                const proteinAmount = parseFloat(info.proteins) || 0;

                if (servingSize > 0) {
                    proteinConcentration = (proteinAmount / servingSize) * 100;
                    totalProtein = (product.weight * proteinConcentration) / 100;
                }
            }
        }

        // Determine origin and processing type from tags (simplified logic)
        let origin: 'Animal' | 'Plant' | 'Blend' = 'Animal'; // Default
        let processingType: 'Isolate' | 'Concentrate' | 'Hydrolyzed' | undefined = undefined;

        if (product.tags) {
            const tagNames = product.tags
                .filter((t: any) => t && t.name)
                .map((t: any) => t.name.toLowerCase());

            if (tagNames.some((t: string) => t.includes('vegetal') || t.includes('vegan') || t.includes('plant'))) {
                origin = 'Plant';
            } else if (tagNames.some((t: string) => t.includes('blend') || t.includes('misto'))) {
                origin = 'Blend';
            }

            if (tagNames.some((t: string) => t.includes('isolado') || t.includes('isolate'))) {
                processingType = 'Isolate';
            } else if (tagNames.some((t: string) => t.includes('hidrolisado') || t.includes('hydrolyzed'))) {
                processingType = 'Hydrolyzed';
            } else if (tagNames.some((t: string) => t.includes('concentrado') || t.includes('concentrate'))) {
                processingType = 'Concentrate';
            }
        }

        return {
            id: product.id,
            brand: product.brand?.display_name || product.brand?.name || 'Unknown',
            name: product.name,
            types: product.category ? [product.category.name] : [],
            processingType: processingType,
            weight: product.weight,
            price: minPrice,
            proteinConcentration: parseFloat(proteinConcentration.toFixed(2)),
            totalProtein: parseFloat(totalProtein.toFixed(2)),
            origin: origin,
            packaging: product.packaging === 'REFILL' ? 'Refill' : 'Container'
        };
    }
}
