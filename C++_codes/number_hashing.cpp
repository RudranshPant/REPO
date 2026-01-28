#include <bits/stdc++.h>
using namespace std;

int main() {

    int n;
    cin >> n;
    int arr[n];
    for (int i = 0; i < n; i++) {
        cin >> arr[i];
    }

    //precompute:
    int hash[13] = {0};//here 13 is the maximum size for simplicity
    for (int i = 0; i < n; i++) {
        hash[arr[i]] += 1;
    }

    int q;//number of queries
    cin >> q;
    while (q--) {
        int number;
        cin >> number;//the actual queries
        // fetching:
        cout << hash[number] << endl;//now here we ask the hash
    }
    return 0;
}