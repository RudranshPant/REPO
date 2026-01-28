// SELECTION SORT//

#include <iostream>
using namespace std;
void selection_sort( int arr[],int n)//Error if arr,n not defined 
{   
    int i;
    for(i=0;i<=n-2;i++)
    
    {
        if(arr[i]>arr[i+1]){
            //Swap logic
            int temp=arr[i];
            arr[i]=arr[i+1];
            arr[i+1]=temp;
        }
    }
    
}



int main(){
    int n,i;
    cout<<"Enter the size of Array:\n";
    cin>>n;
    int arr[n];//Cant initialise as an empty array
    cout<<"Enter the elements of Array\n";
    for(i=0;i<=n-1;i++){
        cin>>arr[i];
        selection_sort(arr,n);
        cout<<"Sorted Array:\n";
        cout<<arr[i]<<" ";
    }
    

}
