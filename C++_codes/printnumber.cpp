#include<iostream>
using namespace std;
class Solution {
public:
    void printNumber() {
        int n;
        //Take input from the user
        cout<<"Enter any value:  ";
        cin>>n;
        cout<<"The entered value is:  "<<n;  
    }
};
int main() {
   Solution obj;
   obj.printNumber();
   return 0;
}