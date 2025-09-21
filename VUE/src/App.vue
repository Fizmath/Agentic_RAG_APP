<script setup>

import axios from 'axios';

import { useToast } from 'primevue/usetoast';
import { ref,onMounted } from 'vue';
const toast = useToast();


const querytext = ref(''); 
const llmtext = ref('');   
const processTime = ref('0.0');
const loading = ref(false); 
const error = ref(null);  
const dbQueryResponse = ref(''); 
const loadingQuery = ref(false);
const metadataCounts = ref([]); 
const loadingUrls = ref(false);
const loadingMetadata = ref(false);
const deleting = ref(false); 
const urlInput = ref(''); 
const llm_model = ref('');
const embeddings_model = ref('');


onMounted(() => {
    fetchConfig();

});

const getLLM = async () => {
    loading.value = true;
    error.value = null;
    llmtext.value = ''
    try {
        const response = await axios.post('/ask', {
            question: querytext.value 
        }, {
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        llmtext.value = response.data.answer; 
        processTime.value = response.data.processing_time; 

    } catch (err) {
        error.value = err.response?.data?.message || err.message;
        console.error('API error:', err);
        toast.add({severity:'error', summary: 'Error', detail: 'Failed to get response from LLM', life: 3000});
    } finally {
        loading.value = false;
    }
};

// 1. Submit URLs endpoint
const submitUrls = async () => {
    if (!urlInput.value.trim()) {
        toast.add({severity:'warn', summary: 'Warning', detail: 'Please enter at least one URL', life: 3000});
        return;
    }
    
    loadingUrls.value = true;
    try {
        // Split URLs by newline and filter out empty ones
        const urls = urlInput.value.split('\n')
            .map(url => url.trim())
            .filter(url => url !== '');
        
        const response = await axios.post('/inject', {
            urls: urls
        }, {
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        toast.add({severity:'success', summary: 'Success', detail: response.data.message, life: 3000});
        urlInput.value = ''; 
    } catch (err) {
        console.error('Error submitting URLs:', err);
        toast.add({severity:'error', summary: 'Error', detail: 'Failed to submit URLs', life: 3000});
    } finally {
        loadingUrls.value = false;
    }
};

// 2. Query database endpoint
const queryDatabase = async () => {
    loadingQuery.value = true;
    try {
        const response = await axios.get('/debug/points');
        dbQueryResponse.value = JSON.stringify(response.data, null, 2);
    } catch (err) {
        console.error('Error querying database:', err);
        dbQueryResponse.value = 'Error fetching data from database';
        toast.add({severity:'error', summary: 'Error', detail: 'Failed to query database', life: 3000});
    } finally {
        loadingQuery.value = false;
    }
};

// 3. Get metadata counts 
const getMetadataCounts = async () => {
    loadingMetadata.value = true;
    try {
        const response = await axios.get('/metadata/counts');
        
        // Convert the object to an array for the table
        const counts = response.data.metadata_counts;
        metadataCounts.value = Object.entries(counts).map(([url, count]) => ({
            url,
            count
        })).sort((a, b) => b.count - a.count); // Sort by count descending
        
    } catch (err) {
        console.error('Error fetching metadata counts:', err);
        toast.add({severity:'error', summary: 'Error', detail: 'Failed to fetch metadata counts', life: 3000});
    } finally {
        loadingMetadata.value = false;
    }
};

// 4. Get config
const fetchConfig = async () => {
    loadingMetadata.value = true;
    try {
        const response = await axios.get('/api/config');
        
        llm_model.value = response.data.llm_model;
        embeddings_model.value = response.data.embeddings_model;
        
    } catch (err) {
        console.error('Error fetching config :', err);
        toast.add({severity:'error', summary: 'Error', detail: 'Failed to fetch config', life: 3000});
    } finally {
        loadingMetadata.value = false;
    }
};
// 5. delete by metadata
const deleteByMetadata = async (url) => {
        deleting.value = true;
        try {
            const response = await axios.post('/delete_by_metadata', {
                url: url
            }, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            metadataCounts.value = metadataCounts.value.filter(item => item.url !== url);
            
            toast.add({severity:'success', summary: 'Success', detail: `Deleted data for ${url}`, life: 3000});
        } catch (err) {
            console.error('Error deleting metadata:', err);
            toast.add({severity:'error', summary: 'Error', detail: 'Failed to delete metadata', life: 3000});
        } finally {
            deleting.value = false;
        }
    };

 
</script>

<template>
  <div class="max-w-6xl mx-auto my-5">
        <!-- Header -->
        <header class="gradient-bg text-white rounded-t-xl p-4 flex items-center justify-between">
            <div class="flex items-center">
                <i class="fas fa-robot text-3xl mr-3"></i>
                <h1 class="text-3xl font-bold">Advanced Agentic RAG Interface </h1>
            </div>
            <div class="flex items-center space-x-2">
                <span class="px-3 py-1 bg-white text-indigo-700 rounded-full text-sm font-semibold">Qdrant Enabled</span>
                <span class="px-3 py-1 bg-white text-indigo-700 rounded-full text-sm font-semibold">Online</span>
            </div>
        </header>

        <!-- Main Content -->
        <div class="chat-container bg-white rounded-b-xl p-5">
            <div class="flex flex-col lg:flex-row">
                <!-- Left Column with Images -->
                <div class="lg:w-2/6  mr-0 lg:mb-0 lg:pr-6">

                    <!-- First Image (280x460) -->
                    <div class="w-full h-[420px] bg-gradient-to-br from-indigo-100 to-purple-100 rounded-xl  flex items-center justify-center mb-30">
                             <Image alt="first Image" width="320" src="/graph.png"  />
                    </div>
                    
                    <!-- Second Image (440x120) -->
                    <div class="second-image w-full h-[100px] bg-gradient-to-br from-purple-200 via-pink-200 rounded-xl p-4 flex items-center ">
                        <div class="flex items-center w-full">
                            <Image alt="second Image" width="250"  src="/qdrant.png"  />

                        </div>
                    </div>
                </div>

                <!-- Right Column with Chat Interface -->
                <div class="lg:w-5/6  ml-0 mr-0">
                    <!-- Stats Bar -->
                    <div class="flex space-x-4 mb-6">
                        <div class="flex-1 bg-indigo-50 p-4 rounded-lg">
                            <div class="text-indigo-700 font-semibold">Ollama model</div>
                            <div class="text-indigo-900 text-xl font-bold">{{ llm_model || 'Loading...' }}</div>
                        </div>
                        <div class="flex-1 bg-indigo-50 p-4 rounded-lg">
                            <div class="text-indigo-700 font-semibold">Response Time</div>
                            <div class="text-indigo-900 text-xl font-bold">{{ processTime }} s</div>
                        </div>
                        <div class="flex-1 bg-indigo-50 p-4 rounded-lg">
                            <div class="text-indigo-700 font-semibold">Embedding model</div>
                            <div class="text-indigo-900 text-xl font-bold">{{ embeddings_model || 'Loading...' }}</div>
                        </div>
                    </div>

                    <!-- Input Area -->
                 <form @submit.prevent="getLLM">
                    <div class="mb-6">
                        <label class="block text-indigo-700 font-semibold mb-2" for="message">
                            <i class="fas fa-comment mr-2"></i>Your Message:
                        </label>
                        <div class="flex">
                            <Textarea 
                                v-model.trim="querytext"
                                type="text" 
                                id="message"
                                placeholder="Type your message here..." 
                                class="message-input flex-1 py-4 px-5 border border-indigo-300 rounded-l-xl focus:outline-none text-lg"
                            </Textarea>
                            <Button  class="submit-btn gradient-bg text-white py-4 px-6 rounded-r-xl text-lg font-semibold"  type="submit"  :disabled="loading"  > {{ loading ? 'Processing...' : 'Chat' }} </Button>
                        </div>
                    </div>
                </form>

                    <!-- Response Area -->
                    <div class="mb-12">
                        <label class="block text-indigo-700 font-semibold mb-2" for="response">
                            <i class="fas fa-reply mr-2"></i>AI Response:
                        </label>
                        <Textarea 
                            id="response"
                            v-model="llmtext"
                            rows="8" 
                            class="response-area w-full p-5 border border-indigo-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none text-lg"
                        </Textarea>
                    </div>

                                <!-- URL Input Section -->
                                <div class="mb-6">
                                    <label class="block text-indigo-700 font-semibold mb-2" for="url">
                                        <i class="fas fa-link mr-2"></i>URL Input: Add data into Qdrant
                                    </label>
                                    <div class="flex flex-col">
                                        <Textarea
                                            v-model="urlInput"
                                            placeholder="Enter URLs here (one per line)..." 
                                            class="url-input flex-1 py-3 px-5 border border-indigo-300 rounded-t-xl focus:outline-none url-textarea"
                                        />
                                        <button 
                                            @click="submitUrls"
                                            :loading="loadingUrls"
                                            class="url-btn   text-white bg-fuchsia-400 py-3 px-6 rounded-b-xl font-semibold"
                                        >
                                            {{ loadingUrls ? 'Injecting...' : 'Submit URLs' }} 
                                    </button>

                                    </div>
                                </div>

                    <!-- Database Query Section -->
                    <div class="mb-6">
                        <label class="block text-indigo-700 font-semibold mb-2" for="dbQuery">
                            <i class="fas fa-database mr-2"></i>Database Query:
                        </label>
                        <Textarea 
                            id="dbQuery"
                            v-model="dbQueryResponse"
                            rows="8" 
                            placeholder="Database query response will appear here..."
                            class="db-input w-full p-4 border border-indigo-300 rounded-t-xl focus:outline-none resize-none"
                        ></Textarea>
                        <div class="flex">
                         <button @click="queryDatabase" :disabled="loadingQuery" class="db-btn flex-1 py-3 bg-pink-400 text-white rounded-bl-xl font-semibold">
                                            <i class="fas fa-search mr-2"></i>{{ loadingQuery ? 'Loading...' : 'Query Database' }}
                                        </button>

<button @click="getMetadataCounts" :disabled="loadingMetadata" class="db-btn flex-1 py-3 bg-purple-400 text-white rounded-br-xl font-semibold">
                                            <i class="fas fa-info-circle mr-2"></i>{{ loadingMetadata ? 'Loading...' : 'Get Metadata Count' }}
                                        </button>
                        </div>
                    </div>
                                <!-- Metadata Dash -->
                                <div>
                                    <label class="block text-indigo-700 font-semibold mb-2" for="metadata">
                                        <i class="fas fa-table mr-2"></i>Metadata Dash:
                                    </label>
                                    <DataTable :value="metadataCounts" class="p-datatable-sm" v-if="metadataCounts.length" responsiveLayout="scroll">
                                        <Column field="url" header="URL" :sortable="true"></Column>
                                        <Column field="count" header="Chunk Count" :sortable="true"></Column>
                                        <Column header="Actions" headerStyle="width: 100px">
                                            <template #body="slotProps">
                                                <Button 
                                                    @click="deleteByMetadata(slotProps.data.url)" 
                                                    :disabled="deleting"
                                                    class="action-btn "
                                                    icon="pi pi-trash"
                                                    v-tooltip.top="'Delete this URL'"
                                                    severity="danger"
                                                />
                                            </template>
                                        </Column>
                                    </DataTable>
                                    <div v-else class="metadata-area w-full p-4 border border-indigo-300 rounded-xl bg-gray-50 text-gray-500">
                                        No metadata available. Click "Get Metadata Count" to load data.
                                    </div>
                                </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <footer class="text-center text-indigo-600 mt-8 p-4">
            <p>Powered by Mahdi Eskandari | Ollama GPU Accelerated  | Vector Database Integration | © 2025</p>
            <a href="https://github.com/Fizmath" target="_blank" rel="noopener noreferrer" class="text-primary font-bold hover:underline">Github</a>
        </footer>
    </div>
    
</template>
    <style>
        body {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            font-family: 'Inter', sans-serif;
        }
        .chat-container {
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }
        .gradient-bg {
            background: linear-gradient(to right, #464871, #7c3aed);
        }
        .message-input:focus, .url-input:focus, .db-input:focus {
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3);
        }
        .submit-btn, .url-btn, .db-btn {
            transition: all 0.3s ease;
        }
        .submit-btn:hover, .url-btn:hover, .db-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 6px -1px rgba(222, 61, 216, 0.1), 0 2px 4px -1px rgba(197, 88, 177, 0.06);
        }
        .response-area, .metadata-area {
            transition: border-color 0.3s ease;
        }
        .second-image {
            transition: transform 0.3s ease;
        }
        .second-image:hover {
            transform: scale(1.05);
        }
        .p-datatable {
            font-size: 0.875rem;
        }
        .url-textarea {
            min-height: 80px;
        }
        .action-btn {
            padding: 0.5rem;
            border-radius: 6px;
            transition: all 0.2s;
        }
        .delete-btn:hover {
            background: linear-gradient(to right, #9e6271, #d00934);
            transform: scale(1.05);
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .stat-box {
            background-color: #eef2ff;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #4f46e5;
        }
    </style>
