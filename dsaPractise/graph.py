num_nodes = 5
edges = [(0,1),(0,4),(1,2),(1,3),(1,4),(2,3),(3,4)]
# num_nodes ,len(edges)

class Graph:
    def __init__(self,num_nodes,edges) :
        self.num_nodes = num_nodes
        self.data = [[] for _ in range(num_nodes)]
        for n1,n2 in edges:
            self.data[n1].append(n2)  
            self.data[n2].append(n1)  
    def __repr__(self):
        return "\n".join(["{}:{}".format(n,neigbours) for n,neigbours in enumerate(self.data)])
    def __str__(self) -> str:
        return str(self.__repr__())
    
    def addNode(self,edges):
        self.num_nodes +=1
        self.data.append([])
        for n1,n2 in edges:
            self.data[n1].append(n2)
            self.data[n2].append(n1)
    def deleteNode(self,deleteNode):
        self.num_nodes -= 1
        del self.data[deleteNode]
    
    
    
    
    
    
    
    
    
    def bfs(graphe,root):
        queue =[]
        discovered =[False] * len(graphe.data)
        discovered[root] = True
        distance = [None] * len(graphe.data)
        parent = [None] * len (graphe.data)
        queue.append(root)
        idx =0
        while idx < len(queue):
            current = queue[idx]
            idx +=1
            for node in graphe.data[current]:
                if not discovered[node]:
                    distance[node] = 1 + distance[current]
                    parent[node] = current
                    discovered[node] = True
                    
                    queue.append(node)
    # tracking parent task
    # make cycle graphe and detect cycle in  a graphe
    def dfs(graphe,root):
        stack = []
        result =[]
        discovered = [False] * len(graphe.data)
        stack.append(root)
        while len(stack) > 0:
            current = stack.pop()
            if not discovered[current]:
                discovered[current] = True
                result.append(current)
            for node in graphe.data[current]:
                if not discovered[node]:
                    stack.append(node)
        return result  
                
garph1 = Graph(num_nodes,edges)



# print(garph1)

garph1.addNode([(5,1),(5, 4)])
garph1.addNode([(6,3),(6,4),(6,0)])
print(garph1)
print('diversion')
# garph1.deleteNode(1) 
print(garph1)

a=10
v=1
while a > 0:
    print(' ' * a ,"*" * v)
    a -=1
    v+=2



# weighted graph
weighted_num_nodes = 9
weighted_edges =[(0,1,3),(0,3,2),(0,8,4),(1,7,4),(2,7,2),(2,3,6),(2,5,1),(3,4,1),(4,8,8),(5,6,8)]
print(len(weighted_edges))

# directed Graph
directed_num_nodes =5
directed_edges =[(0,1),(1,2),(2,3),(2,4),(4,2),(3,0)]
directed = True

# main graphe directed and weighted

class Graphe2:
    def __init__(self,num_of_nodes,edges,directed = False,weighted = False):
        self.num_of_nodes = num_of_nodes
        self.directed = directed
        self.weighted = weighted
        self.data = [[] for _ in range(num_of_nodes)]
        self.weight = [[] for _ in range(num_of_nodes)]
        for edge in edges:
            if self.weighted:
                node1,node2,weight = edge
                self.data[node1].append(node2)
                self.weight[node1].append(weight)
                if not directed:
                    self.data[node2].append(node1)
                    self.weight[node2].append(weight)
            else:
                node1,node2 = edge
                self.data[node1].append(node2)
                if not directed:
                    self.data[node2].append(node1)
                    
                
    def __repr__(self) -> str:
        result = ''
        for 
        return result
        
        
